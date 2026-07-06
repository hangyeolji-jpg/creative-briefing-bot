from datetime import datetime, timedelta

import requests

from briefing.models import Ad


def build_slack_message(brief: str, ads: list[Ad], warnings: list[str]) -> dict:
    """Slack Webhook payload 생성 (Block Kit)."""
    now = datetime.now()
    week_start = (now - timedelta(days=now.weekday())).strftime("%m.%d")
    week_end = (now + timedelta(days=4 - now.weekday())).strftime("%m.%d")

    blocks: list[dict] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"📢 주간 크리에이티브 인사이트 ({week_start}~{week_end})",
            },
        },
        {"type": "section", "text": {"type": "mrkdwn", "text": brief}},
    ]

    if ads:
        lines = "\n".join(f"• <{ad.link}|{ad.advertiser}>" for ad in ads)
        blocks.append({"type": "divider"})
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*이번 주 인기 광고*\n{lines}"},
            }
        )

    if warnings:
        warn_text = "\n".join(f"⚠️ {w}" for w in warnings)
        blocks.append(
            {"type": "context", "elements": [{"type": "mrkdwn", "text": warn_text}]}
        )

    # text는 알림 미리보기/폴백용
    return {"text": f"주간 크리에이티브 인사이트 ({week_start}~{week_end})", "blocks": blocks}


def send_to_slack(payload: dict, webhook_url: str) -> None:
    """Slack Webhook으로 발송. 실패 시 RuntimeError."""
    res = requests.post(webhook_url, json=payload, timeout=10)
    if res.status_code != 200:
        raise RuntimeError(f"Slack 발송 실패: {res.status_code} {res.text}")
