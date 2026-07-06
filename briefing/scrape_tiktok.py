from briefing.config import (
    TIKTOK_REGION,
    TIKTOK_TOP_ADS_URL,
    TIKTOK_TOP_N,
)
from briefing.models import Ad

# TikTok 상세 링크 베이스 (id를 붙여 완성)
_DETAIL_BASE = "https://ads.tiktok.com/business/creativecenter/inspiration/topads/detail/"


def parse_top_ads(payload: dict, top_n: int) -> list[Ad]:
    """TikTok 내부 API 응답(JSON)에서 상위 top_n개 광고를 Ad로 변환.

    실제 필드명은 구현 시 캡처한 응답에 맞춰 조정한다. 누락에 방어적.
    """
    materials = (payload or {}).get("data", {}).get("materials", []) or []
    ads: list[Ad] = []
    for m in materials[:top_n]:
        ad_id = str(m.get("id", ""))
        ads.append(
            Ad(
                advertiser=m.get("brand_name") or "",
                industry=m.get("industry_label") or "",
                likes=m.get("like"),
                ctr=m.get("ctr"),
                format="video" if m.get("video_url") else "image",
                caption=m.get("ad_title") or "",
                link=_DETAIL_BASE + ad_id if ad_id else TIKTOK_TOP_ADS_URL,
            )
        )
    return ads


# NOTE: 아래 scrape_tiktok()의 내부 API URL 매칭 조건("top_ads", "api")과
# JSON 필드명("brand_name", "industry_label", "like", "ctr" 등)은 가정이며,
# 실측 필요(실측 필요): 실제 TikTok Creative Center 응답을 한 번 캡처해
# URL 패턴과 필드명이 맞는지 확인하고, 필요시 on_response 조건과
# parse_top_ads의 .get() 키를 조정한 뒤 픽스처도 갱신해야 한다.
def scrape_tiktok() -> list[Ad]:
    """Playwright로 Top Ads 페이지의 내부 API JSON을 가로채 파싱.

    어떤 실패든 잡아서 빈 리스트를 반환한다(봇은 계속 진행).
    """
    captured: dict = {}
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
                # 내부 top_ads API 응답만 캡처
                if "top_ads" in response.url and "api" in response.url:
                    try:
                        captured.update(response.json())
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
    except Exception as e:  # noqa: BLE001 - 부분 실패 허용
        print(f"[TikTok 스크래핑 실패: {e}]")
        return []

    return parse_top_ads(captured, TIKTOK_TOP_N)
