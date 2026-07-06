from briefing.models import Ad
from briefing.analyze import build_prompt


def _ad(name):
    return Ad(advertiser=name, industry="뷰티", likes=500, ctr=0.04,
              format="video", caption="여름 세일", link="https://x/1")


def test_prompt_includes_ad_data():
    prompt = build_prompt([_ad("브랜드A")])
    assert "브랜드A" in prompt
    assert "여름 세일" in prompt
    # 출력 형식 4개 섹션이 지시에 포함되는지
    assert "트렌드" in prompt
    assert "후킹" in prompt
    assert "포맷" in prompt
    assert "적용" in prompt


def test_prompt_handles_empty_ads():
    prompt = build_prompt([])
    assert "웹" in prompt  # 웹 검색으로 보완하라는 지시
    assert "한국어" in prompt
