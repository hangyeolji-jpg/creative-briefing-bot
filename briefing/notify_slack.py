from datetime import datetime, timedelta

import requests

from briefing.models import Ad

_FALLBACK_BRIEF = "이번 주 브리핑 내용이 비어 있습니다. 아래 원본 링크를 참고하세요."


def _chunk_text(text: str, limit: int = 2900) -> list[str]:
    """Split *text* into chunks of at most *limit* chars, preferring newline boundaries."""
    if not text:
        return [text]
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for line in text.splitlines(keepends=True):
        # If a single line is longer than limit, hard-split it
        while len(line) > limit:
            chunks.append(line[:limit])
            line = line[limit:]
        if current_len + len(line) > limit:
            chunks.append("".join(current))
            current = []
            current_len = 0
        current.append(line)
        current_len += len(line)
    if current:
        chunks.append("".join(current))
    return chunks


def build_slack_message(brief: str, ads: list[Ad], warnings: list[str]) -> dict:
    """Slack Webhook payload 생성 (Block Kit)."""
    now = datetime.now()
    week_start = (now - timedelta(days=now.weekday())).strftime("%m.%d")
    week_end = (now + timedelta(days=4 - now.weekday())).strftime("%m.%d")

    safe_brief = brief.strip() if brief.strip() else _FALLBACK_BRIEF
    brief_chunks = _chunk_text(safe_brief)

    blocks: list[dict] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"📢 주간 크리에이티브 인사이트 ({week_start}~{week_end})",
            },
        },
    ]
    for chunk in brief_chunks:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": chunk}})

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
