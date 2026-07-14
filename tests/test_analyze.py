import pytest

from briefing.analyze import analyze, build_prompt, is_retryable
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
