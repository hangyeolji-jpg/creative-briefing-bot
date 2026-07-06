import json

from briefing.models import Ad
from briefing.notify_slack import build_slack_message


def _ad(name, link):
    return Ad(advertiser=name, industry="뷰티", likes=100, ctr=0.02,
             format="video", caption="cap", link=link)


def test_message_includes_brief_and_links():
    ads = [_ad("브랜드A", "https://x/1"), _ad("브랜드B", "https://x/2")]
    payload = build_slack_message("이번 주 요약", ads, warnings=[])
    text = json.dumps(payload, ensure_ascii=False)
    assert "이번 주 요약" in text
    assert "브랜드A" in text
    assert "https://x/1" in text
    assert "https://x/2" in text
    assert "blocks" in payload


def test_message_shows_warning_when_present():
    payload = build_slack_message("요약", [], warnings=["TikTok 수집 실패"])
    text = json.dumps(payload, ensure_ascii=False)
    assert "TikTok 수집 실패" in text


def test_message_handles_no_ads_without_warning():
    payload = build_slack_message("요약", [], warnings=[])
    text = json.dumps(payload, ensure_ascii=False)
    assert "요약" in text
