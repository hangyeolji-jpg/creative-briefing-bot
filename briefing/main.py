import os
import sys
from datetime import datetime, timedelta, timezone

from briefing.analyze import analyze
from briefing.notify_slack import build_slack_message, send_to_slack
from briefing.save_briefing import save_briefing
from briefing.scrape_tiktok import scrape_tiktok

_KST = timezone(timedelta(hours=9))
_DATA_DIR = "web/data"


def _flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes")


def run() -> None:
    api_key = os.environ.get("GEMINI_API_KEY")
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if not api_key or not webhook_url:
        print("❌ GEMINI_API_KEY / SLACK_WEBHOOK_URL 환경변수 필요")
        sys.exit(1)

    dry_run = _flag("DRY_RUN")
    skip_slack = _flag("SKIP_SLACK")  # 아카이브만 채우고 팀 채널은 건드리지 않을 때

    warnings: list[str] = []

    print("🔍 TikTok Top Ads 수집 중...")
    ads = scrape_tiktok()
    if not ads:
        warnings.append("TikTok 인기 광고 수집 실패 — 웹 검색 기반으로 작성됨")

    print("🤖 Gemini 분석 중...")
    brief = analyze(ads, api_key)  # 실패 시 예외 → 비정상 종료

    payload = build_slack_message(brief, ads, warnings)

    # dry-run: API 키·스크래핑·분석까지 실제로 검증하되, 팀 채널 발송과
    # 아카이브 커밋 같은 되돌리기 어려운 부수효과는 건너뛴다.
    if dry_run:
        print("🧪 DRY_RUN — Slack 발송/아카이브 저장 건너뜀\n")
        print("=" * 60)
        print(brief)
        print("=" * 60)
        for w in warnings:
            print(f"⚠️ {w}")
        print(f"\n수집된 광고: {len(ads)}건")
        print("✅ dry-run 완료!")
        return

    if skip_slack:
        print("⏭️ SKIP_SLACK — 발송 생략, 아카이브만 저장")
    else:
        print("📨 Slack 발송 중...")
        send_to_slack(payload, webhook_url)  # 실패 시 RuntimeError → 비정상 종료

    date = datetime.now(_KST).strftime("%Y-%m-%d")
    try:
        save_briefing(date, brief, ads, warnings, _DATA_DIR)
        print("🗄️ 아카이브 저장 완료")
    except Exception as e:  # noqa: BLE001 - 아카이브 실패는 비치명적
        print(f"[아카이브 저장 실패(비치명적): {e}]")

    print("✅ 완료!")
