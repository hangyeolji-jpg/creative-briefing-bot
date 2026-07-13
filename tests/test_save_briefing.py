import json
from pathlib import Path

from briefing.models import Ad
from briefing.save_briefing import save_briefing


def _ads():
    return [
        Ad(advertiser="A", industry="뷰티", likes=10, ctr=0.1,
           format="video", caption="c1", link="https://x/1",
           thumbnail="https://cdn/cover0.jpg"),
        Ad(advertiser="B", industry="패션", likes=None, ctr=None,
           format="image", caption="c2", link="https://x/2", thumbnail=None),
    ]


def _ok_fetch(saved):
    def _f(url, dest):
        Path(dest).write_bytes(b"jpegbytes")
        saved.append((url, str(dest)))
        return True
    return _f


def test_writes_briefing_json_and_index(tmp_path):
    saved = []
    rec = save_briefing("2026-07-13", "# 트렌드\n본문", _ads(), [],
                        tmp_path, generated_at="2026-07-13T00:00:00Z",
                        fetch=_ok_fetch(saved))

    brief_file = tmp_path / "briefings" / "2026-07-13.json"
    assert brief_file.exists()
    data = json.loads(brief_file.read_text(encoding="utf-8"))
    assert data["date"] == "2026-07-13"
    assert data["generated_at"] == "2026-07-13T00:00:00Z"
    assert data["ads"][0]["advertiser"] == "A"
    # 다운로드 성공한 썸네일은 로컬 상대경로로 치환
    assert data["ads"][0]["thumbnail"] == "thumbs/2026-07-13/00.jpg"
    assert (tmp_path / "thumbs" / "2026-07-13" / "00.jpg").exists()
    # thumbnail 없는 광고는 null
    assert data["ads"][1]["thumbnail"] is None

    index = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
    assert index["briefings"][0]["date"] == "2026-07-13"
    assert index["briefings"][0]["ad_count"] == 2
    assert index["briefings"][0]["headline"] == "트렌드"  # 마크다운 기호 제거


def test_thumbnail_download_failure_sets_null(tmp_path):
    def _fail(url, dest):
        return False
    data = save_briefing("2026-07-13", "b", _ads(), [], tmp_path,
                         generated_at="t", fetch=_fail)
    assert data["ads"][0]["thumbnail"] is None  # 실패 → null, 예외 없음


def test_index_upsert_and_sorts_desc(tmp_path):
    save_briefing("2026-07-06", "older", _ads(), [], tmp_path,
                  generated_at="t", fetch=lambda u, d: False)
    save_briefing("2026-07-13", "newer", _ads(), [], tmp_path,
                  generated_at="t", fetch=lambda u, d: False)
    # 같은 날짜 재저장은 중복 생성 없이 갱신
    save_briefing("2026-07-13", "newer-v2", _ads(), [], tmp_path,
                  generated_at="t", fetch=lambda u, d: False)

    index = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
    dates = [b["date"] for b in index["briefings"]]
    assert dates == ["2026-07-13", "2026-07-06"]  # 최신순, 중복 없음
    assert index["briefings"][0]["headline"] == "newer-v2"
