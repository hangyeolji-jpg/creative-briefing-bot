import pytest

import briefing.main as main
from briefing.models import Ad


def _ad():
    return Ad(advertiser="A", industry="뷰티", likes=1, ctr=0.01,
             format="video", caption="c", link="https://x/1")


def _env(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.delenv("DRY_RUN", raising=False)


def test_dry_run_skips_archive(monkeypatch, capsys):
    _env(monkeypatch)
    monkeypatch.setenv("DRY_RUN", "true")
    monkeypatch.setattr(main, "scrape_tiktok", lambda: [_ad()])
    monkeypatch.setattr(main, "analyze", lambda ads, api_key: "요약본문")

    def _must_not_call(*a, **k):
        raise AssertionError("dry-run에서 호출되면 안 됨")

    monkeypatch.setattr(main, "save_briefing", _must_not_call)

    main.run()  # save_briefing이 불리면 AssertionError로 실패

    out = capsys.readouterr().out
    assert "DRY_RUN" in out
    assert "요약본문" in out  # 브리핑 내용은 로그로 확인 가능해야 함


def test_run_saves_archive(monkeypatch):
    calls = {}
    _env(monkeypatch)
    monkeypatch.setattr(main, "scrape_tiktok", lambda: [_ad()])
    monkeypatch.setattr(main, "analyze", lambda ads, api_key: "요약")
    monkeypatch.setattr(main, "save_briefing",
                        lambda *a, **k: calls.update(saved=True, args=a))

    main.run()

    assert calls.get("saved") is True
    # 위치 인자: date, brief, ads, warnings, data_dir
    assert calls["args"][1] == "요약"
    assert calls["args"][4] == "web/data"


def test_run_exits_when_api_key_missing(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(SystemExit):
        main.run()


def test_run_continues_when_scrape_fails(monkeypatch):
    calls = {}
    _env(monkeypatch)
    monkeypatch.setattr(main, "scrape_tiktok", lambda: [])
    monkeypatch.setattr(main, "analyze", lambda ads, api_key: "웹서치 기반 요약")
    monkeypatch.setattr(main, "save_briefing",
                        lambda *a, **k: calls.update(args=a))

    main.run()

    # 위치 인자: date, brief, ads, warnings, data_dir
    assert calls["args"][1] == "웹서치 기반 요약"
    warnings = calls["args"][3]
    assert any("수집" in w for w in warnings)  # 수집 실패 경고가 남아야 함


def test_run_archive_failure_is_fatal(monkeypatch):
    _env(monkeypatch)
    monkeypatch.setattr(main, "scrape_tiktok", lambda: [_ad()])
    monkeypatch.setattr(main, "analyze", lambda ads, api_key: "요약")

    def _boom(*a, **k):
        raise IOError("disk full")

    monkeypatch.setattr(main, "save_briefing", _boom)

    # 아카이브가 유일한 산출물이므로 저장 실패는 비정상 종료로 드러나야 한다.
    with pytest.raises(IOError):
        main.run()
