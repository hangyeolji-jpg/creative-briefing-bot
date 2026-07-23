import os
import sys
from datetime import datetime, timedelta, timezone

from briefing.analyze import analyze
from briefing.save_briefing import save_briefing
from briefing.scrape_tiktok import scrape_tiktok

# Slack 발송은 파이프라인에서 제거됐다 — 브리핑은 웹 대시보드로만 본다.
# 재연동할 때를 위해 briefing/notify_slack.py 는 그대로 남겨둔다.

_KST = timezone(timedelta(hours=9))
_DATA_DIR = "web/data"


def _flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes")


def run() -> None:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("❌ GEMINI_API_KEY 환경변수 필요")
        sys.exit(1)

    dry_run = _flag("DRY_RUN")

    warnings: list[str] = []

    print("🔍 TikTok Top Ads 수집 중...")
    ads = scrape_tiktok()
    if not ads:
        warnings.append("TikTok 인기 광고 수집 실패 — 웹 검색 기반으로 작성됨")

    print("🤖 Gemini 분석 중...")
    brief = analyze(ads, api_key)  # 실패 시 예외 → 비정상 종료

    # dry-run: API 키·스크래핑·분석까지 실제로 검증하되, 아카이브 커밋 같은
    # 되돌리기 어려운 부수효과는 건너뛴다.
    if dry_run:
        print("🧪 DRY_RUN — 아카이브 저장 건너뜀\n")
        print("=" * 60)
        print(brief)
        print("=" * 60)
        for w in warnings:
            print(f"⚠️ {w}")
        print(f"\n수집된 광고: {len(ads)}건")
        print("✅ dry-run 완료!")
        return

    # 아카이브(대시보드 데이터)가 이 봇의 유일한 산출물이다. 저장이 실패하면
    # 보여줄 게 없으므로 예외를 삼키지 않고 비정상 종료해 CI에 드러낸다.
    date = datetime.now(_KST).strftime("%Y-%m-%d")
    save_briefing(date, brief, ads, warnings, _DATA_DIR)
    print("🗄️ 아카이브 저장 완료")
    print("✅ 완료!")
