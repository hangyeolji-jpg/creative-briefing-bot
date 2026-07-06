from briefing.models import Ad


def test_ad_holds_all_fields():
    ad = Ad(
        advertiser="브랜드A",
        industry="뷰티",
        likes=1200,
        ctr=0.031,
        format="video",
        caption="지금 사면 50% 할인",
        link="https://ads.tiktok.com/detail/123",
    )
    assert ad.advertiser == "브랜드A"
    assert ad.likes == 1200
    assert ad.ctr == 0.031
    assert ad.link.endswith("/123")


def test_ad_allows_missing_metrics():
    ad = Ad(
        advertiser="브랜드B",
        industry="",
        likes=None,
        ctr=None,
        format="image",
        caption="",
        link="https://ads.tiktok.com/detail/456",
    )
    assert ad.likes is None
    assert ad.ctr is None
