import statistics
import time

from briefing.config import BASE_DELAY_SEC, MAX_RETRIES, MODEL, USE_GOOGLE_SEARCH
from briefing.models import Ad

# 재시도할 상태코드: 429(quota/rate limit) + 일시적 서버 오류
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_RETRYABLE_TEXT = ("resource_exhausted", "rate limit", "quota", "unavailable", "overloaded")


def _format_ads(ads: list[Ad]) -> str:
    if not ads:
        if USE_GOOGLE_SEARCH:
            return (
                "이번 주 TikTok Top Ads 자동 수집 데이터가 없습니다. "
                "웹 검색으로 '이번 주 인기 광고 / 크리에이티브 트렌드'를 "
                "직접 검색해 트렌드를 파악하세요."
            )
        return (
            "이번 주 TikTok Top Ads 자동 수집 데이터가 없습니다. "
            "웹 검색도 사용할 수 없으니, 확실히 알고 있는 최신 크리에이티브 "
            "트렌드 지식만으로 작성하고 근거가 약한 내용은 단정하지 마세요."
        )
    rows = []
    for i, ad in enumerate(ads, 1):
        likes = "-" if ad.likes is None else f"{ad.likes:,}"
        ctr = "-" if ad.ctr is None else f"{ad.ctr:.2%}"
        dur = "-" if not ad.duration else f"{ad.duration:.0f}초"
        obj = ad.objective or "-"
        rows.append(
            f"{i}. 광고주={ad.advertiser or '미상'} / 업종={ad.industry} / 좋아요={likes} "
            f"/ CTR={ctr} / 포맷={ad.format} / 길이={dur} / 캠페인목표={obj} "
            f"/ 카피={ad.caption} / 링크={ad.link}"
        )
    return "\n".join(rows)


def summarize_metrics(ads: list[Ad]) -> str:
    """집계 수치를 미리 계산해 프롬프트에 넣는다.

    모델이 20건을 눈대중으로 훑어 '대부분 CTR 70~97%' 같은 잘못된 일반화를
    하는 것을 막는다(실제 범위는 9~97%였다). 계산은 코드가, 해석은 모델이.
    """
    if not ads:
        return ""

    lines = [f"- 광고 수: {len(ads)}건"]

    ctrs = [a.ctr for a in ads if a.ctr is not None]
    if ctrs:
        lines.append(
            f"- CTR: 최저 {min(ctrs):.1%} / 중앙값 {statistics.median(ctrs):.1%} "
            f"/ 최고 {max(ctrs):.1%}"
        )

    likes = [a.likes for a in ads if a.likes is not None]
    if likes:
        lines.append(
            f"- 좋아요: 최저 {min(likes):,} / 중앙값 {statistics.median(likes):,.0f} "
            f"/ 최고 {max(likes):,}"
        )

    durations = [a.duration for a in ads if a.duration]
    if durations:
        lines.append(
            f"- 영상 길이(초): 최단 {min(durations):.0f} / 중앙값 "
            f"{statistics.median(durations):.0f} / 최장 {max(durations):.0f}"
        )

    formats: dict[str, int] = {}
    for a in ads:
        formats[a.format] = formats.get(a.format, 0) + 1
    lines.append(
        "- 포맷 구성: " + ", ".join(f"{k} {v}건" for k, v in sorted(formats.items()))
    )

    objectives: dict[str, int] = {}
    for a in ads:
        if a.objective:
            objectives[a.objective] = objectives.get(a.objective, 0) + 1
    if objectives:
        ranked = sorted(objectives.items(), key=lambda kv: -kv[1])
        lines.append(
            "- 캠페인 목표 구성: " + ", ".join(f"{k} {v}건" for k, v in ranked)
        )

    return "\n".join(lines)


def build_prompt(ads: list[Ad]) -> str:
    ad_block = _format_ads(ads)
    stats = summarize_metrics(ads)
    stats_block = (
        f"\n[집계 수치 — 코드가 계산한 값이므로 수치 인용 시 반드시 이것을 쓸 것]\n{stats}\n"
        if stats
        else ""
    )
    search_line = (
        "필요하면 Google 검색으로 이번 주 광고 트렌드 기사를 추가로 찾아 보완하세요."
        if USE_GOOGLE_SEARCH
        else "웹 검색 도구는 사용할 수 없습니다. 아래 수집 데이터를 근거로 작성하세요."
    )
    return f"""당신은 퍼포먼스 마케터를 위한 크리에이티브 인사이트 분석가입니다.
아래는 이번 주 TikTok Creative Center의 인기 광고(Top Ads) 수집 데이터입니다.
{search_line}

[수집 데이터]
{ad_block}
{stats_block}
목록은 인기순입니다. 순위가 높다고 CTR이 높은 것은 아니니 둘을 뒤섞지 마세요.

위 내용을 바탕으로 아래 형식으로 이번 주 크리에이티브 인사이트를 정리하세요.

형식:
1. 이번 주 주목할 트렌드 (3가지, 각 1~2줄)
2. 주목할 후킹/카피 패턴 (2~3가지, 예시 포함)
3. 포맷 트렌드 (어떤 포맷이 뜨고 있는지)
4. 우리 소재 기획에 적용할 수 있는 포인트 (1~2가지)

수치 인용 규칙(엄수):
- CTR·좋아요 같은 수치를 언급할 때는 위 [집계 수치]의 값만 쓰세요.
- 상위 몇 건을 보고 "대부분 ~%대" 같이 전체로 일반화하지 마세요.
- 특정 광고를 예로 들 때는 그 광고의 수치임을 명시하세요.

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

    config = None
    if USE_GOOGLE_SEARCH:
        config = types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
        )

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=config,
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
