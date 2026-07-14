# 크리에이티브 브리핑 아카이브 (웹)

봇이 `web/data/`에 커밋한 주간 브리핑을 열람하는 정적 대시보드.

## 로컬 실행

```bash
python -m http.server 8000 --directory web
# http://localhost:8000
```

Basic Auth는 Vercel Edge Middleware로만 동작하므로 로컬 정적 서버에서는 실행되지 않는다 — 인증 없이 열린다.

## Vercel 배포 (최초 1회)

1. Vercel에서 New Project → 이 GitHub 저장소 선택.
2. **Root Directory = `web`** 로 지정.
3. Framework Preset = **Other** (빌드 없음).
4. Environment Variables 에 `SITE_PASSWORD` = 팀 공용 비밀번호 추가.
   **Production/Preview 모든 환경에 넣을 것** — 미설정 환경은 503으로 잠긴다.
5. Deploy.

이후 봇이 매주 `web/data`를 push하면 Vercel이 자동 재배포한다.
접속 시 브라우저 Basic Auth 창에서 아이디는 아무 값, 비번은 `SITE_PASSWORD`.

사이트가 503("SITE_PASSWORD 환경변수가 설정되지 않아…")을 뱉으면 해당 환경에 변수가 없다는 뜻이다.
