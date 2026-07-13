import json
from pathlib import Path

from briefing.scrape_tiktok import build_industry_map, parse_top_ads

FIXTURES = Path(__file__).parent / "fixtures"
FIXTURE = FIXTURES / "tiktok_top_ads.json"
FILTERS_FIXTURE = FIXTURES / "tiktok_filters.json"


def _payload():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _filters():
    return json.loads(FILTERS_FIXTURE.read_text(encoding="utf-8"))


def _industry_map():
    return build_industry_map(_filters())


def test_parse_maps_fields_to_ads():
    ads = parse_top_ads(_payload(), top_n=20, industry_map=_industry_map())
    assert len(ads) == 2
    first = ads[0]
    assert first.advertiser == "브랜드A"
    assert first.industry == "뷰티"  # industry_key -> filters value 치환
    assert first.likes == 1234
    assert first.ctr == 0.031
    assert first.caption == "여름 세일 지금"
    assert first.format == "video"  # video_info 있음
    assert "aaa111" in first.link
    assert first.link.endswith("/pc/en")  # 실측 확인된 상세 링크 형식


def test_parse_respects_top_n():
    ads = parse_top_ads(_payload(), top_n=1)
    assert len(ads) == 1


def test_parse_tolerates_missing_fields():
    ads = parse_top_ads(_payload(), top_n=20, industry_map=_industry_map())
    second = ads[1]
    assert second.ctr is None  # null 허용
    assert second.advertiser == "브랜드B"
    assert second.format == "image"  # video_info 없음


def test_parse_handles_empty_or_malformed():
    assert parse_top_ads({}, top_n=20) == []
    assert parse_top_ads({"data": {}}, top_n=20) == []


def test_build_industry_map():
    m = _industry_map()
    assert m["label_23125000000"] == "뷰티"
    assert m["label_23130000000"] == "패션"


def test_parse_without_industry_map_falls_back_to_raw_key():
    # 매핑이 없으면 원본 코드값을 그대로 둔다(정보 손실 방지)
    ads = parse_top_ads(_payload(), top_n=1)
    assert ads[0].industry == "label_23125000000"
