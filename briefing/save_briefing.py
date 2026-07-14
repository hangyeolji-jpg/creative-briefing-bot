import json
import re
import urllib.request
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from briefing.models import Ad

# 헤드라인 추출용: 줄 앞의 마크다운 접두사(제목/리스트/인용)와 강조 기호만 제거.
_MD_PREFIX = re.compile(r"^\s*(?:#{1,6}\s*|[-*+]\s+|>\s+)")
_MD_EMPHASIS = re.compile(r"\*\*|__")


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


def _write_json(path: Path, obj) -> None:
    """임시 파일에 쓰고 교체 — 도중에 죽어도 반쪽짜리 JSON이 남지 않는다."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    tmp.replace(path)


def _headline(brief: str, limit: int = 80) -> str:
    """브리핑 첫 유효 줄에서 마크다운 기호를 떼어 목록 미리보기용 헤드라인 생성."""
    for raw in (brief or "").splitlines():
        line = _MD_EMPHASIS.sub("", _MD_PREFIX.sub("", raw)).strip()
        if line:
            return line[:limit]
    return ""


def _rebuild_entries(briefings_dir: Path) -> list[dict]:
    """저장된 상세 JSON들로 index 항목을 복원."""
    entries = []
    for path in briefings_dir.glob("*.json"):
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        entries.append(
            {
                "date": rec.get("date", path.stem),
                "ad_count": len(rec.get("ads", [])),
                "headline": _headline(rec.get("brief", "")),
            }
        )
    return entries


def _load_index(index_path: Path, briefings_dir: Path) -> dict:
    """index.json을 읽되, 손상됐으면 상세 JSON들로 재구축한다.

    그냥 예외를 던지면 상위(main)가 비치명적으로 삼켜서 이후 모든 실행이
    상세 파일만 쌓고 index는 영영 복구되지 않는다 — 대시보드가 조용히 빈다.
    """
    if not index_path.exists():
        return {"briefings": []}
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
        if isinstance(index, dict) and isinstance(index.get("briefings"), list):
            return index
    except (ValueError, OSError):
        pass
    return {"briefings": _rebuild_entries(briefings_dir)}


def _update_index(
    data_dir: Path, briefings_dir: Path, date: str, brief: str, ad_count: int
) -> None:
    index_path = data_dir / "index.json"
    index = _load_index(index_path, briefings_dir)
    entry = {"date": date, "ad_count": ad_count, "headline": _headline(brief)}
    others = [b for b in index["briefings"] if b.get("date") != date]
    index["briefings"] = sorted(
        [entry, *others], key=lambda b: b.get("date", ""), reverse=True
    )
    _write_json(index_path, index)


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

    # 같은 날짜 재실행 시 광고 수가 줄면 이전 썸네일이 고아로 남아 커밋에 누적된다.
    if thumbs_dir.exists():
        for stale in thumbs_dir.glob("*.jpg"):
            stale.unlink()

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
    _write_json(briefings_dir / f"{date}.json", record)
    _update_index(data_dir, briefings_dir, date, brief, len(ad_dicts))
    return record
