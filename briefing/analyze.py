import time

from briefing.config import BASE_DELAY_SEC, MAX_RETRIES, MODEL
from briefing.models import Ad

# 재시도할 상태코드: 429(quota/rate limit) + 일시적 서버 오류
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_RETRYABLE_TEXT = ("resource_exhausted", "rate limit", "quota", "unavailable", "overloaded")


def _format_ads(ads: list[Ad]) -> str:
    if not ads:
        return (
            "이번 주 TikTok Top Ads 자동 수집 데이터가 없습니다. "
            "웹 검색으로 '이번 주 인기 광고 / 크리에이티브 트렌드'를 "
            "직접 검색해 트렌드를 파악하세요."
        )
    rows = []
    for i, ad in enumerate(ads, 1):
        likes = "-" if ad.likes is None else f"{ad.likes:,}"
        ctr = "-" if ad.ctr is None else f"{ad.ctr:.2%}"
        rows.append(
            f"{i}. 광고주={ad.advertiser} / 업종={ad.industry} / 좋아요={likes} "
            f"/ CTR={ctr} / 포맷={ad.format} / 카피={ad.caption} / 링크={ad.link}"
        )
    return "\n".join(rows)


def build_prompt(ads: list[Ad]) -> str:
    ad_block = _format_ads(ads)
    return f"""당신은 퍼포먼스 마케터를 위한 크리에이티브 인사이트 분석가입니다.
아래는 이번 주 TikTok Creative Center의 인기 광고(Top Ads) 수집 데이터입니다.
필요하면 Google 검색으로 이번 주 광고 트렌드 기사를 추가로 찾아 보완하세요.

[수집 데이터]
{ad_block}

위 내용을 바탕으로 아래 형식으로 이번 주 크리에이티브 인사이트를 정리하세요.

형식:
1. 이번 주 주목할 트렌드 (3가지, 각 1~2줄)
2. 주목할 후킹/카피 패턴 (2~3가지, 예시 포함)
3. 포맷 트렌드 (어떤 포맷이 뜨고 있는지)
4. 우리 소재 기획에 적용할 수 있는 포인트 (1~2가지)

수집된 데이터/검색 결과에 없는 내용은 억측하지 말고 근거 기반으로만 작성하세요.
한국어로, Slack에서 읽기 좋게 간결하게 작성하세요."""


def is_retryable(exc: Exception) -> bool:
    """quota/rate-limit/일시적 서버 오류인지 판정.

    SDK 예외 계층에 기대지 않고 상태코드와 메시지로 본다 — google-genai의
    예외 타입이 버전마다 달라 타입만 보면 조용히 재시도를 놓친다.
    """
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if isinstance(code, int) and code in _RETRYABLE_STATUS:
        return True
    text = str(exc).lower()
    return any(t in text for t in _RETRYABLE_TEXT)


def _build_client(api_key: str):
    from google import genai

    return genai.Client(api_key=api_key)


def _generate(client, prompt: str) -> str:
    from google.genai import types

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
        ),
    )
    return (response.text or "").strip()


def analyze(ads: list[Ad], api_key: str, *, client=None, sleep=time.sleep) -> str:
    """Gemini로 인사이트 브리핑 생성. Google 검색 grounding 사용.

    429(quota)에서 지수 백오프로 재시도한다 — 재시도 없이 죽던 것이 v1의 문제였다.
    """
    client = client or _build_client(api_key)

    for attempt in range(MAX_RETRIES):
        try:
            brief = _generate(client, build_prompt(ads))
        except Exception as exc:
            last = attempt == MAX_RETRIES - 1
            if last or not is_retryable(exc):
                raise
            delay = BASE_DELAY_SEC * (2**attempt)
            print(f"[Gemini 일시 오류 — {delay}초 후 재시도 {attempt + 1}/{MAX_RETRIES}: {exc}]")
            sleep(delay)
            continue

        if brief:
            return brief
        # 빈 응답도 일시적일 수 있어 재시도하되, 끝까지 비면 실패로 본다.
        if attempt == MAX_RETRIES - 1:
            raise RuntimeError("Gemini가 빈 브리핑을 반환했습니다")
        sleep(BASE_DELAY_SEC * (2**attempt))

    raise RuntimeError("Gemini 분석 실패 (재시도 소진)")
