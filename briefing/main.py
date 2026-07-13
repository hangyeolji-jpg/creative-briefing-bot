import os
import sys
from datetime import datetime, timedelta, timezone

from briefing.analyze import analyze
from briefing.notify_slack import build_slack_message, send_to_slack
from briefing.save_briefing import save_briefing
from briefing.scrape_tiktok import scrape_tiktok

_KST = timezone(timedelta(hours=9))
_DATA_DIR = "web/data"


def run() -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if not api_key or not webhook_url:
        print("❌ ANTHROPIC_API_KEY / SLACK_WEBHOOK_URL 환경변수 필요")
        sys.exit(1)

    warnings: list[str] = []

    print("🔍 TikTok Top Ads 수집 중...")
    ads = scrape_tiktok()
    if not ads:
        warnings.append("TikTok 인기 광고 수집 실패 — 웹 검색 기반으로 작성됨")

    print("🤖 Claude 분석 중...")
    brief = analyze(ads, api_key)  # 실패 시 예외 → 비정상 종료

    print("📨 Slack 발송 중...")
    payload = build_slack_message(brief, ads, warnings)
    send_to_slack(payload, webhook_url)  # 실패 시 RuntimeError → 비정상 종료

    date = datetime.now(_KST).strftime("%Y-%m-%d")
    try:
        save_briefing(date, brief, ads, warnings, _DATA_DIR)
        print("🗄️ 아카이브 저장 완료")
    except Exception as e:  # noqa: BLE001 - 아카이브 실패는 비치명적
        print(f"[아카이브 저장 실패(비치명적): {e}]")

    print("✅ 완료!")
