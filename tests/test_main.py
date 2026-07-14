import pytest

import briefing.main as main
from briefing.models import Ad


def _ad():
    return Ad(advertiser="A", industry="뷰티", likes=1, ctr=0.01,
             format="video", caption="c", link="https://x/1")


def _env(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hook")
    monkeypatch.delenv("DRY_RUN", raising=False)
    monkeypatch.delenv("SKIP_SLACK", raising=False)


def test_skip_slack_still_saves_archive(monkeypatch):
    calls = {}
    _env(monkeypatch)
    monkeypatch.setenv("SKIP_SLACK", "true")
    monkeypatch.setattr(main, "scrape_tiktok", lambda: [_ad()])
    monkeypatch.setattr(main, "analyze", lambda ads, api_key: "요약")

    def _must_not_send(*a, **k):
        raise AssertionError("SKIP_SLACK인데 발송되면 안 됨")

    monkeypatch.setattr(main, "send_to_slack", _must_not_send)
    monkeypatch.setattr(main, "save_briefing", lambda *a, **k: calls.update(saved=True))

    main.run()

    assert calls.get("saved") is True  # 아카이브는 저장돼야 함


def test_dry_run_skips_slack_and_archive(monkeypatch, capsys):
    _env(monkeypatch)
    monkeypatch.setenv("DRY_RUN", "true")
    monkeypatch.setattr(main, "scrape_tiktok", lambda: [_ad()])
    monkeypatch.setattr(main, "analyze", lambda ads, api_key: "요약본문")

    def _must_not_call(*a, **k):
        raise AssertionError("dry-run에서 호출되면 안 됨")

    monkeypatch.setattr(main, "send_to_slack", _must_not_call)
    monkeypatch.setattr(main, "save_briefing", _must_not_call)

    main.run()  # 부수효과 함수가 불리면 AssertionError로 실패

    out = capsys.readouterr().out
    assert "DRY_RUN" in out
    assert "요약본문" in out  # 브리핑 내용은 로그로 확인 가능해야 함


def test_run_happy_path(monkeypatch):
    sent = {}
    _env(monkeypatch)
    monkeypatch.setattr(main, "scrape_tiktok", lambda: [_ad()])
    monkeypatch.setattr(main, "analyze", lambda ads, api_key: "요약")
    monkeypatch.setattr(main, "send_to_slack", lambda payload, url: sent.update(payload=payload))
    monkeypatch.setattr(main, "save_briefing", lambda *a, **k: None)

    main.run()

    text = str(sent["payload"])
    assert "요약" in text
    assert "A" in text


def test_run_exits_when_env_vars_missing(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    with pytest.raises(SystemExit):
        main.run()


def test_run_continues_when_scrape_fails(monkeypatch):
    sent = {}
    _env(monkeypatch)
    monkeypatch.setattr(main, "scrape_tiktok", lambda: [])
    monkeypatch.setattr(main, "analyze", lambda ads, api_key: "웹서치 기반 요약")
    monkeypatch.setattr(main, "send_to_slack", lambda payload, url: sent.update(payload=payload))
    monkeypatch.setattr(main, "save_briefing", lambda *a, **k: None)

    main.run()

    text = str(sent["payload"])
    assert "웹서치 기반 요약" in text
    assert "수집" in text


def test_run_saves_archive(monkeypatch):
    calls = {}
    _env(monkeypatch)
    monkeypatch.setattr(main, "scrape_tiktok", lambda: [_ad()])
    monkeypatch.setattr(main, "analyze", lambda ads, api_key: "요약")
    monkeypatch.setattr(main, "send_to_slack", lambda payload, url: None)
    monkeypatch.setattr(main, "save_briefing",
                        lambda *a, **k: calls.update(saved=True, args=a))

    main.run()

    assert calls.get("saved") is True
    # 위치 인자: date, brief, ads, warnings, data_dir
    assert calls["args"][1] == "요약"
    assert calls["args"][4] == "web/data"


def test_run_archive_failure_is_non_fatal(monkeypatch):
    _env(monkeypatch)
    monkeypatch.setattr(main, "scrape_tiktok", lambda: [_ad()])
    monkeypatch.setattr(main, "analyze", lambda ads, api_key: "요약")
    monkeypatch.setattr(main, "send_to_slack", lambda payload, url: None)

    def _boom(*a, **k):
        raise IOError("disk full")

    monkeypatch.setattr(main, "save_briefing", _boom)

    main.run()  # 예외가 전파되면 안 됨 (테스트가 실패로 잡음)
