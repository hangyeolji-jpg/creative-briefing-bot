# 크리에이티브 브리핑 아카이브 웹 — 설계 문서

작성일: 2026-07-13

## 배경 / 문제

주간 크리에이티브 브리핑 봇(`creative-briefing-bot`)은 매주 월요일 Slack으로
브리핑을 발송하지만, **발송 후 아무것도 남기지 않는다.** 지난 브리핑을 다시
보려면 Slack 스크롤을 뒤져야 하고, 시간이 지나면 사실상 유실된다.

팀이 지난 브리핑을 한곳에서 아카이브로 열람할 수 있는 **웹 대시보드**가 필요하다.

## 목표

- 봇이 매주 생성한 브리핑을 **영구 보관**(아카이브)
- 팀이 웹에서 **날짜별 브리핑 목록 → 상세**를 열람
- 상세 화면: 브리핑 본문 + 그 주 인기 광고 카드(썸네일·업종·좋아요·CTR·원본 링크)
- **팀 전용 비공개** (링크만으로는 접근 불가)
- 기존 Slack 발송 흐름은 그대로 유지

## 비목표 (YAGNI)

- 계정별 로그인/권한 (공용 비밀번호 하나로 충분)
- 검색/필터/태그 (주 1건 소량이라 최신순 목록으로 충분, 추후)
- 브리핑 편집/삭제 UI (봇이 쓰고 사람은 읽기만)
- 데이터베이스 (git 저장소가 곧 아카이브 스토어)
- 코멘트/공유/알림 등 협업 기능

## 아키텍처

```
[GitHub Actions 주간 cron]  (기존 워크플로 확장)
  scrape_tiktok → analyze → notify_slack     (기존 그대로)
                          ↘ save_briefing (신규)
                            web/data/briefings/YYYY-MM-DD.json 기록
                            web/data/index.json 갱신 (목록 인덱스)
                            web/data/thumbs/YYYY-MM-DD/{id}.jpg 다운로드
                            → git commit & push (GITHUB_TOKEN)
        │  (push가 Vercel 자동 재배포 트리거)
        ▼
[Vercel]  같은 repo, Root Directory = web/, 정적 배포(빌드 없음)
  middleware.js : 모든 요청에 HTTP Basic Auth (env SITE_PASSWORD) → 비공개
  index.html    : 정적 · vanilla JS SPA. data/index.json 로드 → 목록,
                  선택 시 data/briefings/<date>.json 로드 → 본문 + 광고 카드
  styles.css    : Apple 스타일 가이드 (단일 블루 #0066cc, 17px 본문 등)
  data/         : 봇이 커밋한 JSON 아카이브 + 로컬 썸네일
```

언어/스택: **프레임워크 없음.** HTML/CSS/vanilla JS. 빌드 도구 없음.
저장소: 기존 `creative-briefing-bot` 안 `web/` 하위 폴더 (봇=쓰기, 웹=읽기 단일 관리).

## 데이터 계약 (Data Contract)

### `web/data/briefings/YYYY-MM-DD.json` — 브리핑 1건

```json
{
  "date": "2026-07-13",
  "generated_at": "2026-07-13T00:05:00Z",
  "brief": "…트렌드 3 / 후킹·카피 패턴 / 포맷 트렌드 / 적용 포인트 (마크다운)…",
  "warnings": ["TikTok 수집 실패 — 웹 검색 기반" 등],
  "ads": [
    {
      "advertiser": "브랜드명",
      "industry": "Women's Clothing",
      "likes": 1234,
      "ctr": 0.15,
      "format": "video",
      "caption": "광고 카피",
      "link": "https://ads.tiktok.com/business/creativecenter/topads/<id>/pc/en",
      "thumbnail": "thumbs/2026-07-13/<id>.jpg"
    }
  ]
}
```

- `thumbnail`: **로컬 상대경로.** TikTok cover URL은 서명·만료(`x-expires`)되어
  아카이브에서 곧 깨지므로, 저장 시 이미지를 내려받아 repo에 함께 커밋한다.
  다운로드 실패 시 `thumbnail`은 `null`(카드는 텍스트만 표시).

### `web/data/index.json` — 목록 인덱스 (최신순)

```json
{
  "briefings": [
    { "date": "2026-07-13", "ad_count": 20, "headline": "브리핑 첫 줄 요약" },
    { "date": "2026-07-06", "ad_count": 18, "headline": "…" }
  ]
}
```

`headline`은 목록에서 미리보기로 쓸 짧은 요약(브리핑 첫 문장 또는 트렌드 헤드).

## 컴포넌트

### 봇 측 (Python)

#### `briefing/models.py` — `Ad`에 `thumbnail` 추가
- `thumbnail: str | None` 필드 추가 (기본 None)

#### `briefing/scrape_tiktok.py` — cover 캡처
- `parse_top_ads`에서 `m["video_info"]["cover"]`를 `Ad.thumbnail`로 저장
  (원본 서명 URL; 다운로드는 저장 단계에서)

#### `briefing/save_briefing.py` (신규)
- 책임: 브리핑 1건을 아카이브로 영속화
- 입력: `date`, `brief(str)`, `ads(list[Ad])`, `warnings(list[str])`
- 동작:
  1. 각 광고 썸네일(cover URL)을 `web/data/thumbs/<date>/<id>.jpg`로 다운로드
     (실패 시 해당 thumbnail=null, 계속 진행)
  2. 광고의 `thumbnail`을 로컬 상대경로로 치환
  3. `web/data/briefings/<date>.json` 기록
  4. `web/data/index.json`을 로드→해당 날짜 항목 upsert→최신순 정렬→기록
- 순수 파일 I/O. 네트워크는 썸네일 다운로드뿐(방어적, 실패 허용)
- 경로 상수는 `config.py` 또는 인자로 주입 가능하게(테스트 용이)

#### `briefing/main.py` — 저장 호출 추가
- 순서: scrape → analyze → **notify_slack** → **save_briefing**
- save_briefing 실패는 **비치명적**(로그 + 경고). 이미 Slack 발송은 성공했으므로
  아카이브 저장 실패로 전체를 실패시키지 않는다.
- `date`는 실행 시각(KST) 기준 `YYYY-MM-DD`

#### `.github/workflows/weekly_briefing.yml` — commit & push
- `permissions: contents: write`
- 봇 실행 후, `web/data/` 변경분을 커밋하고 push하는 스텝 추가
  (`git add web/data && git commit -m "chore: archive <date>" && git push`,
  변경 없으면 skip)

### 웹 측 (정적, `web/`)

#### `web/middleware.js` — 비공개 게이트
- Vercel Edge Middleware. 모든 경로에 HTTP Basic Auth 요구.
- 자격 비교 대상: 환경변수 `SITE_PASSWORD`(사용자명은 고정 또는 무시).
- 불일치 시 401 + `WWW-Authenticate: Basic`.
- 폴백: Edge Middleware가 정적 배포에서 문제되면 `/api/gate` 서버리스
  함수 + 쿠키 방식으로 대체(플랜 단계에서 우선 Edge Middleware 시도).

#### `web/index.html` + `web/app.js` + `web/styles.css`
- 단일 페이지. 로드 시 `data/index.json` fetch → 상단 날짜 리스트 렌더(최신순).
- 항목 클릭 → `data/briefings/<date>.json` fetch → 본문(마크다운 간이 렌더)
  + 광고 카드 그리드.
- 광고 카드: 썸네일(있으면) · 광고주 · 업종 배지 · 좋아요/CTR · 카피 ·
  "원본 보기" 링크(새 탭).
- 상태: 로딩/빈 아카이브/개별 로드 실패 처리.
- 디자인: 메모리의 Apple 스타일 가이드 준수(단일 블루 #0066cc, 17px 본문,
  그라디언트 없음, 카드 그림자 절제).

#### `web/vercel.json` (필요 시)
- 정적 프리셋. 라우팅/헤더 설정이 필요하면 여기.

## 데이터 흐름

```
봇 실행 → save_briefing → web/data/*.json (+thumbs) → git push
      → Vercel 재배포 → 사용자가 Basic Auth 통과 → index.html
      → index.json(목록) → 선택 → briefings/<date>.json(상세)
```

## 에러 처리 요약

| 지점 | 실패 | 처리 |
|------|------|------|
| 썸네일 다운로드 | URL 만료/네트워크 | 해당 thumbnail=null, 계속 |
| save_briefing | 파일 I/O 오류 | 로그 + 경고, 전체는 성공 처리(Slack은 이미 발송) |
| git push | 충돌/권한 | Action 로그 실패 표시(브리핑 자체는 이미 발송됨) |
| 웹: index.json 없음 | 최초/유실 | "아직 브리핑 없음" 빈 상태 |
| 웹: 개별 json 로드 실패 | 파일 없음 | 해당 항목만 오류 메시지 |
| 인증 | 비번 불일치 | 401 재요청 |

## 테스트

- `save_briefing`: 임시 디렉터리에 브리핑 기록 → JSON 스키마·index upsert·
  최신순 정렬 검증. 썸네일 다운로드는 목/스킵. 다운로드 실패 시 null 처리 검증.
- `parse_top_ads`: `thumbnail`이 `video_info.cover`에서 채워지는지(+누락 시 None) 추가.
- `main`: save_briefing 실패가 전체를 실패시키지 않는지(비치명적) 통합 테스트.
- 웹: 수동 확인(로컬에서 `python -m http.server`로 `web/` 서빙 후 육안 검증).

## 시크릿 / 설정

- Vercel 환경변수: `SITE_PASSWORD` (신규, 팀 공용 비번)
- Vercel 프로젝트: Root Directory = `web`, Framework Preset = Other(정적)
- GitHub Actions: 기존 `ANTHROPIC_API_KEY`, `SLACK_WEBHOOK_URL` 유지.
  워크플로에 `contents: write` 권한 추가.
- config 상수: 아카이브 경로(`web/data/...`), 썸네일 폴더

## 마이그레이션 / 영향

- 기존 스크래핑/분석/발송 로직은 변경 없음(썸네일 필드 1개 추가 제외).
- 새 디렉터리 `web/`. 봇 실행 시마다 `web/data/`가 커밋되어 커진다
  (주 1건 JSON + 썸네일 ~20장). 장기적으로 썸네일이 누적되나 소용량.
- 첫 배포 시 데이터가 없으면 웹은 빈 상태. 원하면 과거 브리핑을 수동 백필 가능(선택).

## 열린 질문 / 후속(YAGNI 보류)

- 썸네일 누적 용량이 커지면 오래된 것 정리(예: 최근 N주만 보관) — 지금은 불필요.
- 검색/업종 필터 — 아카이브가 쌓이면 추후.
- 광고 성과 추이(주간 비교 차트) — 데이터가 쌓인 뒤 별도 스펙.
