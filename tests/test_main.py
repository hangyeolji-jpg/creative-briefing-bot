import briefing.main as main
from briefing.models import Ad


def _ad():
    return Ad(advertiser="A", industry="뷰티", likes=1, ctr=0.01,
             format="video", caption="c", link="https://x/1")


def test_run_happy_path(monkeypatch):
    sent = {}
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hook")
    monkeypatch.setattr(main, "scrape_tiktok", lambda: [_ad()])
    monkeypatch.setattr(main, "analyze", lambda ads, api_key: "요약")
    monkeypatch.setattr(main, "send_to_slack", lambda payload, url: sent.update(payload=payload))

    main.run()

    text = str(sent["payload"])
    assert "요약" in text
    assert "A" in text


def test_run_continues_when_scrape_fails(monkeypatch):
    sent = {}
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hook")
    monkeypatch.setattr(main, "scrape_tiktok", lambda: [])  # 수집 실패 → 빈 리스트
    monkeypatch.setattr(main, "analyze", lambda ads, api_key: "웹서치 기반 요약")
    monkeypatch.setattr(main, "send_to_slack", lambda payload, url: sent.update(payload=payload))

    main.run()

    text = str(sent["payload"])
    assert "웹서치 기반 요약" in text
    assert "수집" in text  # 경고 문구 포함
