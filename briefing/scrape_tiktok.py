from briefing.config import (
    TIKTOK_REGION,
    TIKTOK_TOP_ADS_URL,
    TIKTOK_TOP_N,
)
from briefing.models import Ad

# TikTok Top Ads 상세 페이지 링크 (실측 확인: .../topads/{id}/pc/en 이 200)
_DETAIL_BASE = "https://ads.tiktok.com/business/creativecenter/topads/"

# 실측 확인된 내부 API 경로 (2026-07 캡처)
_LIST_API = "top_ads/v2/list"       # 인기 광고 목록
_FILTERS_API = "top_ads/v2/filters"  # industry_key -> 사람이 읽는 이름 매핑


def _detail_link(ad_id: str) -> str:
    return f"{_DETAIL_BASE}{ad_id}/pc/en" if ad_id else TIKTOK_TOP_ADS_URL


def build_industry_map(filters_payload: dict) -> dict:
    """filters 응답에서 industry label(코드) -> 사람이 읽는 value 매핑을 만든다.

    실측 구조: data.industry = [{id, value, label, parent_id}, ...]
    광고의 industry_key는 여기 label(예: "label_23125000000")과 일치한다.
    """
    industries = ((filters_payload or {}).get("data", {}) or {}).get("industry", []) or []
    return {
        i.get("label"): i.get("value")
        for i in industries
        if i.get("label") and i.get("value")
    }


def parse_top_ads(payload: dict, top_n: int, industry_map: dict | None = None) -> list[Ad]:
    """TikTok top_ads/v2/list 응답(JSON)에서 상위 top_n개 광고를 Ad로 변환.

    실측 필드(2026-07): materials[] 각 항목은
      id, brand_name, ad_title, like, ctr, industry_key, video_info(중첩) 등.
    industry_map이 있으면 industry_key를 사람이 읽는 이름으로 치환한다.
    누락에 방어적으로 동작한다.
    """
    industry_map = industry_map or {}
    materials = (payload or {}).get("data", {}).get("materials", []) or []
    ads: list[Ad] = []
    for m in materials[:top_n]:
        ad_id = str(m.get("id", ""))
        industry_key = m.get("industry_key") or ""
        ads.append(
            Ad(
                advertiser=m.get("brand_name") or "",
                industry=industry_map.get(industry_key, industry_key),
                likes=m.get("like"),
                ctr=m.get("ctr"),
                format="video" if m.get("video_info") else "image",
                caption=m.get("ad_title") or "",
                link=_detail_link(ad_id),
            )
        )
    return ads


def scrape_tiktok() -> list[Ad]:
    """Playwright로 Top Ads 페이지의 내부 API JSON을 가로채 파싱.

    같은 페이지 로드에서 목록(list)과 필터(filters) 응답이 모두 자동으로 뜨므로
    둘 다 캡처해, 업종 코드를 사람이 읽는 이름으로 치환한다.
    어떤 실패든 잡아서 빈 리스트를 반환한다(봇은 계속 진행).
    """
    captured: dict = {}
    filters: dict = {}
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
                )
            )

            def on_response(response):
                url = response.url
                if _LIST_API in url:
                    try:
                        captured.update(response.json())
                    except Exception:
                        pass
                elif _FILTERS_API in url:
                    try:
                        filters.update(response.json())
                    except Exception:
                        pass

            page.on("response", on_response)
            page.goto(
                f"{TIKTOK_TOP_ADS_URL}?region={TIKTOK_REGION}",
                wait_until="networkidle",
                timeout=60000,
            )
            page.wait_for_timeout(3000)  # 지연 후 XHR 완료 대기
            browser.close()
            return parse_top_ads(captured, TIKTOK_TOP_N, build_industry_map(filters))
    except Exception as e:  # noqa: BLE001 - 부분 실패 허용
        print(f"[TikTok 스크래핑 실패: {e}]")
        return []
