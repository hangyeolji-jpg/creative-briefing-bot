import os

# Gemini 모델. 구버전은 신규 사용자에게 404가 나므로(2.5-flash가 그랬다)
# 모델이 또 바뀌면 코드 수정 없이 GEMINI_MODEL 환경변수로 덮어쓴다.
MODEL = os.environ.get("GEMINI_MODEL") or "gemini-3.1-flash-lite"

# Google Search grounding. 무료 티어에는 grounding 할당량이 없어 429가 난다
# (모델 단독 호출은 통과, 검색 툴을 붙이면 429). 유료 전환 시 1로 켠다.
USE_GOOGLE_SEARCH = os.environ.get("USE_GOOGLE_SEARCH", "0").strip().lower() in ("1", "true", "yes")

# 429/5xx 재시도 — v1이 quota(429)에서 그냥 죽던 것이 v2의 발단이었다.
MAX_RETRIES = 5
BASE_DELAY_SEC = 4  # 지수 백오프: 4, 8, 16, 32초

# TikTok Creative Center Top Ads 필터 기본값
TIKTOK_REGION = "KR"
TIKTOK_PERIOD_DAYS = 7
TIKTOK_TOP_N = 20
TIKTOK_TOP_ADS_URL = (
    "https://ads.tiktok.com/business/creativecenter/inspiration/topads/pc/en"
)
