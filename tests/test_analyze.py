import pytest

from briefing.analyze import analyze, build_prompt, is_retryable, summarize_metrics
from briefing.config import MAX_RETRIES
from briefing.models import Ad


def _ad(name):
    return Ad(advertiser=name, industry="뷰티", likes=500, ctr=0.04,
              format="video", caption="여름 세일", link="https://x/1")


class _Quota(Exception):
    """google-genai의 429를 흉내 (code 속성 보유)."""
    code = 429


class _FakeClient:
    """models.generate_content 만 흉내내는 최소 클라이언트."""

    def __init__(self, outcomes):
        self._outcomes = list(outcomes)
        self.calls = 0
        self.models = self

    def generate_content(self, **kwargs):
        self.calls += 1
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return type("R", (), {"text": outcome})()


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


def _spread():
    """실제 데이터처럼 CTR 편차가 큰 광고 묶음 (9% ~ 97%)."""
    return [
        Ad(advertiser="1위", industry="게임", likes=142, ctr=0.09,
           format="video", caption="c1", link="https://x/1"),
        Ad(advertiser="중간", industry="뷰티", likes=900, ctr=0.55,
           format="video", caption="c2", link="https://x/2"),
        Ad(advertiser="고효율", industry="패션", likes=50, ctr=0.97,
           format="image", caption="c3", link="https://x/3"),
    ]


def test_summary_uses_full_range_not_top_items():
    s = summarize_metrics(_spread())
    # 1위(9%)만 보고 일반화하지 못하도록 최저·중앙·최고를 모두 준다
    assert "9.0%" in s and "97.0%" in s and "55.0%" in s
    assert "광고 수: 3건" in s
    assert "video 2건" in s and "image 1건" in s


def test_summary_handles_missing_metrics():
    ads = [Ad(advertiser="A", industry="뷰티", likes=None, ctr=None,
              format="video", caption="c", link="https://x/1")]
    s = summarize_metrics(ads)
    assert "광고 수: 1건" in s
    assert "CTR" not in s  # 값이 없으면 지어내지 않는다
    assert summarize_metrics([]) == ""


def test_prompt_carries_stats_and_citation_rule():
    prompt = build_prompt(_spread())
    assert "[집계 수치" in prompt
    assert "97.0%" in prompt
    assert "일반화하지 마세요" in prompt
    assert "순위가 높다고 CTR이 높은 것은 아니" in prompt


def test_is_retryable_detects_quota_and_ignores_others():
    assert is_retryable(_Quota("RESOURCE_EXHAUSTED"))
    assert is_retryable(Exception("429 rate limit exceeded"))
    assert not is_retryable(ValueError("invalid api key"))


def test_retries_on_quota_then_succeeds():
    client = _FakeClient([_Quota("quota"), _Quota("quota"), "브리핑 본문"])
    slept = []

    brief = analyze([_ad("A")], "k", client=client, sleep=slept.append)

    assert brief == "브리핑 본문"
    assert client.calls == 3
    assert slept == [4, 8]  # 지수 백오프


def test_gives_up_after_max_retries():
    client = _FakeClient([_Quota("quota")] * MAX_RETRIES)
    with pytest.raises(_Quota):
        analyze([_ad("A")], "k", client=client, sleep=lambda s: None)
    assert client.calls == MAX_RETRIES


def test_non_retryable_error_raises_immediately():
    client = _FakeClient([ValueError("API key not valid")])
    with pytest.raises(ValueError):
        analyze([_ad("A")], "k", client=client, sleep=lambda s: None)
    assert client.calls == 1  # 재시도하지 않음
