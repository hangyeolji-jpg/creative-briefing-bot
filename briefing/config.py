# Gemini 모델 (무료 티어 사용 가능)
MODEL = "gemini-2.5-flash"

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
