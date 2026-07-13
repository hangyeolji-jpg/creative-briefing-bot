import json
import urllib.request
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from briefing.models import Ad


def _default_fetch(url: str, dest: Path) -> bool:
    """cover 이미지를 dest로 저장. 성공 True, 실패 False(예외 삼킴)."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = r.read()
        Path(dest).write_bytes(data)
        return True
    except Exception:
        return False


def _headline(brief: str, limit: int = 80) -> str:
    """브리핑 첫 유효 줄에서 마크다운 기호를 떼어 목록 미리보기용 헤드라인 생성."""
    for raw in (brief or "").splitlines():
        line = raw.lstrip("#*-  ").strip()
        if line:
            return line[:limit]
    return ""


def _update_index(data_dir: Path, date: str, brief: str, ad_count: int) -> None:
    index_path = data_dir / "index.json"
    if index_path.exists():
        index = json.loads(index_path.read_text(encoding="utf-8"))
    else:
        index = {"briefings": []}
    entry = {"date": date, "ad_count": ad_count, "headline": _headline(brief)}
    others = [b for b in index.get("briefings", []) if b.get("date") != date]
    index["briefings"] = sorted(
        [entry, *others], key=lambda b: b.get("date", ""), reverse=True
    )
    index_path.write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def save_briefing(
    date: str,
    brief: str,
    ads: list[Ad],
    warnings: list[str],
    data_dir,
    *,
    generated_at: str | None = None,
    fetch=_default_fetch,
) -> dict:
    """브리핑 1건을 아카이브(JSON + 로컬 썸네일 + index)로 영속화하고 record 반환."""
    data_dir = Path(data_dir)
    briefings_dir = data_dir / "briefings"
    thumbs_dir = data_dir / "thumbs" / date
    briefings_dir.mkdir(parents=True, exist_ok=True)

    ad_dicts: list[dict] = []
    for i, ad in enumerate(ads):
        d = asdict(ad)
        thumb_rel = None
        if ad.thumbnail:
            thumbs_dir.mkdir(parents=True, exist_ok=True)
            dest = thumbs_dir / f"{i:02d}.jpg"
            if fetch(ad.thumbnail, dest):
                thumb_rel = f"thumbs/{date}/{i:02d}.jpg"
        d["thumbnail"] = thumb_rel
        ad_dicts.append(d)

    record = {
        "date": date,
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        "brief": brief,
        "warnings": warnings,
        "ads": ad_dicts,
    }
    (briefings_dir / f"{date}.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _update_index(data_dir, date, brief, len(ad_dicts))
    return record
