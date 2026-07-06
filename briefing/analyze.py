import anthropic

from briefing.config import MODEL, WEB_SEARCH_TOOL_TYPE
from briefing.models import Ad


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
필요하면 web_search 도구로 이번 주 광고 트렌드 기사를 추가로 찾아 보완하세요.

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


def analyze(ads: list[Ad], api_key: str) -> str:
    """Claude로 인사이트 브리핑 생성. web_search 도구 허용."""
    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        tools=[{"type": WEB_SEARCH_TOOL_TYPE, "name": "web_search"}],
        messages=[{"role": "user", "content": build_prompt(ads)}],
    )
    # 서버 도구(web_search) 사용 시 text 블록만 이어붙임
    parts = [b.text for b in response.content if b.type == "text"]
    return "\n".join(p for p in parts if p).strip()
