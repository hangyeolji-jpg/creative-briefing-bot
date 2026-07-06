import json
from unittest.mock import patch, MagicMock

from briefing.models import Ad
from briefing.notify_slack import build_slack_message, send_to_slack


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


def test_send_raises_on_non_200():
    resp = MagicMock(status_code=500, text="Internal Server Error")
    with patch("briefing.notify_slack.requests.post", return_value=resp):
        try:
            send_to_slack({"text": "test"}, "https://hooks.slack.com/test")
            assert False, "expected RuntimeError"
        except RuntimeError as e:
            assert "500" in str(e)


def test_send_ok_on_200():
    resp = MagicMock(status_code=200, text="ok")
    with patch("briefing.notify_slack.requests.post", return_value=resp):
        send_to_slack({"text": "test"}, "https://hooks.slack.com/test")  # should not raise
