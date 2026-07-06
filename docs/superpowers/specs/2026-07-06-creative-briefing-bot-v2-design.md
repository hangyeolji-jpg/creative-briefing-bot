# 주간 크리에이티브 인사이트 브리핑 봇 v2 — 설계 문서

작성일: 2026-07-06

## 배경 / 문제

기존 봇(`creative_briefing_bot.py`)은 매주 월요일 Slack으로 광고 크리에이티브
인사이트를 발송한다. 하지만 두 가지 근본 문제가 있다.

1. **수집 실패(무증상).** TikTok Creative Center, Meta Ad Library 등은 JS로
   렌더링되는 SPA다. `requests` + `BeautifulSoup`로는 광고 데이터가 없는 껍데기
   HTML만 받는다. 예외가 안 나서 부실한 텍스트가 그대로 AI에 전달된다.
2. **Gemini API quota(429) 오류.** 발단이 된 문제. 재시도/백오프 로직이 없어
   quota를 만나면 그냥 실패한다.

또한 광고 라이브러리들은 일반 상업 광고의 성과 지표(지출/CTR/ROAS)를 공개하지
않는다. 예외적으로 **TikTok Creative Center의 Top Ads**는 인기순 랭킹과 일부
참여 지표(좋아요, 전환율 등)를 공개한다 → 이것이 유일하게 신뢰할 수 있는
"인기/효율 광고" 소스다.

## 목표

- 매주 월요일 09:00(KST) Slack으로 크리에이티브 인사이트 브리핑 발송
- 소재 기획에 참고할 인사이트(트렌드/후킹패턴/포맷/적용포인트) 중심
- 각 광고의 원본 링크를 함께 제공(비전 분석은 하지 않음)
- 대상 브랜드/키워드 지정 없이 **트렌드/인기 광고 자동 큐레이션**

## 비목표 (YAGNI)

- 광고 썸네일/영상 비전 분석 안 함 (텍스트 + 링크만)
- 특정 경쟁사/브랜드/키워드 감시 안 함 (자동 큐레이션만)
- Meta Ad Library / Google 투명성 센터 직접 스크래핑 안 함
  (인기 랭킹 피드가 없어 자동 큐레이션에 부적합 → 웹서치로 보완)
- Notion/이메일 등 추가 채널 안 함 (Slack 단일)

## 아키텍처

```
GitHub Actions (cron: 매주 월 09:00 KST = 00:00 UTC)
   │
   ├─ scrape_tiktok.py   Playwright(chromium)로 TikTok Top Ads(KR) 수집  [주력]
   │
   ├─ analyze.py         Claude API + web_search 도구로 브리핑 생성
   │
   ├─ notify_slack.py    Slack Webhook 발송
   │
   └─ main.py            오케스트레이션 + 부분 실패 처리
```

언어: Python (기존 인프라 유지). 실행: GitHub Actions 주간 cron.

### 모듈

#### `scrape_tiktok.py`
- 책임: TikTok Creative Center Top Ads 페이지에서 인기 광고 목록 수집
- 도구: Playwright (headless chromium). GitHub Actions에서
  `playwright install --with-deps chromium`로 설치
- 필터 기본값: **지역 KR / 기간 최근 7일 / 정렬 인기순 / 전체 업종**
- 반환: `list[Ad]`
  ```python
  @dataclass
  class Ad:
      advertiser: str        # 광고주/브랜드명
      industry: str          # 업종 라벨
      likes: int | None      # 좋아요 수
      ctr: float | None      # 노출 대비 클릭률(공개 시)
      format: str            # 영상/이미지 등
      caption: str           # 광고 카피/텍스트(있으면)
      link: str              # 원본 광고 상세 링크
  ```
- 예의: 요청 간 지연, 상단 N개(기본 20)만 수집. 내부 참고용, 재배포 안 함.
- 실패 시: 예외를 잡아 빈 리스트 반환(봇은 계속 진행). 사이트 개편으로
  셀렉터가 깨질 수 있음을 감안해 파싱을 방어적으로 작성.

#### `analyze.py`
- 책임: 수집 데이터 + 웹 검색으로 한국어 인사이트 브리핑 생성
- 모델: `claude-opus-4-8`
- 도구: `web_search_20260209` (Opus 4.8 지원) — Claude가 직접 "이번 주 화제
  광고/트렌드" 기사를 검색해 보완
- 입력: `list[Ad]`를 구조화 텍스트로 프롬프트에 삽입
- 출력 형식(프롬프트로 고정):
  1. 이번 주 주목할 트렌드 (3가지)
  2. 주목할 후킹/카피 패턴 (2~3가지 예시)
  3. 포맷 트렌드
  4. 우리 소재 기획 적용 포인트 (1~2가지)
- 원칙: 수집된 데이터/검색 결과에 없는 내용은 억측하지 않음
- 에러: Anthropic SDK 기본 재시도(429/5xx 지수 백오프) 활용.
  `RateLimitError` / `APIStatusError`를 분기 처리해 로그 남김.
- 인증: `ANTHROPIC_API_KEY` 환경변수 (GitHub Actions Secret)

#### `notify_slack.py`
- 책임: 브리핑 + 원본 링크를 Slack Webhook으로 발송
- 포맷: Block Kit — 상단 요약 텍스트 + 하단 "이번 주 인기 광고" 링크 목록
  (광고주명 + 링크). 수집 실패/부분 실패 시 하단에 안내 문구
- 인증: `SLACK_WEBHOOK_URL` 환경변수
- 실패 시: 상태코드 로그, 비정상 종료 코드로 알림

#### `main.py`
- 순서: `scrape_tiktok()` → `analyze(ads)` → `notify_slack(brief, ads, warnings)`
- 부분 실패 정책:
  - 스크래핑 실패(빈 리스트) → 경고 플래그, 웹서치 기반으로 브리핑 계속 진행
  - 분석 실패 → 비정상 종료(발송 안 함)
  - 발송 실패 → 비정상 종료

### 데이터 흐름

```
scrape_tiktok() → list[Ad]  (실패 시 [] + warning)
        ↓
analyze(ads)    → brief(str)  (web_search 허용)
        ↓
notify_slack(brief, ads, warnings) → Slack 발송
```

## 에러 처리 요약

| 지점 | 실패 유형 | 처리 |
|------|-----------|------|
| Playwright | 타임아웃/셀렉터 변경 | 예외 캐치 → 빈 리스트 + warning, 계속 진행 |
| Claude API | 429/5xx | SDK 기본 백오프 재시도, 그래도 실패 시 비정상 종료 |
| Claude API | 4xx(키 오류 등) | 즉시 실패, 로그 |
| Slack | 발송 실패 | 로그 + 비정상 종료 코드 |

## 테스트

- `notify_slack`: 픽스처 데이터로 Block Kit 메시지 포매팅 단위 테스트
- `analyze`: `list[Ad]` → 프롬프트 문자열 빌드 검증 (API 호출은 목/스킵)
- `scrape_tiktok`: 저장된 HTML 픽스처로 파싱 로직 검증 (네트워크 없이)
- `main`: 스크래핑 실패 시 계속 진행하는지 통합 테스트(의존성 목)

## 시크릿 / 설정

GitHub Actions Secrets:
- `ANTHROPIC_API_KEY` (신규)
- `SLACK_WEBHOOK_URL` (기존)
- `GEMINI_API_KEY` (제거)

설정 상수(코드 상단 또는 config):
- TikTok 지역=KR, 기간=7일, 정렬=인기순, 업종=전체, 상위 N=20
- 모델=`claude-opus-4-8`

## 마이그레이션 노트

- 기존 `creative_briefing_bot.py`의 3개 크롤러 함수 및 `analyze_with_gemini`
  전량 대체
- `google-genai`, `beautifulsoup4` 의존성 제거, `anthropic` + `playwright` 추가
- GitHub Actions 워크플로에 `playwright install --with-deps chromium` 단계 추가
```
