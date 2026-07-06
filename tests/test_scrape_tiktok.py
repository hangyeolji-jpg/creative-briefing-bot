import json
from pathlib import Path

from briefing.scrape_tiktok import parse_top_ads

FIXTURE = Path(__file__).parent / "fixtures" / "tiktok_top_ads.json"


def _payload():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_parse_maps_fields_to_ads():
    ads = parse_top_ads(_payload(), top_n=20)
    assert len(ads) == 2
    first = ads[0]
    assert first.advertiser == "브랜드A"
    assert first.industry == "뷰티"
    assert first.likes == 1234
    assert first.ctr == 0.031
    assert first.caption == "여름 세일 지금"
    assert "aaa111" in first.link


def test_parse_respects_top_n():
    ads = parse_top_ads(_payload(), top_n=1)
    assert len(ads) == 1


def test_parse_tolerates_missing_fields():
    ads = parse_top_ads(_payload(), top_n=20)
    second = ads[1]
    assert second.ctr is None  # null 허용
    assert second.advertiser == "브랜드B"


def test_parse_handles_empty_or_malformed():
    assert parse_top_ads({}, top_n=20) == []
    assert parse_top_ads({"data": {}}, top_n=20) == []
