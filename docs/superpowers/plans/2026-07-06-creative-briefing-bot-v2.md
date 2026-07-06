# 주간 크리에이티브 인사이트 브리핑 봇 v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 기존 봇의 Gemini 의존 + 무증상 크롤링 실패를 걷어내고, Playwright로 TikTok Top Ads(KR)를 실제 수집한 뒤 Claude API(웹서치 포함)로 주간 크리에이티브 인사이트를 만들어 Slack으로 발송한다.

**Architecture:** Python 패키지 `briefing/`로 스크래퍼·분석·발송을 모듈 분리하고, 루트 `creative_briefing_bot.py`가 진입점으로 `briefing.main.run()`을 호출한다. 부분 실패 허용: TikTok 스크래핑이 실패해도 Claude 웹서치 기반으로 브리핑을 만들어 발송한다.

**Tech Stack:** Python 3.11, `anthropic` SDK, `playwright`(chromium), `requests`(Slack), `pytest`. GitHub Actions 주간 cron.

## Global Constraints

- Python 버전: 3.11 (GitHub Actions와 일치)
- 모델 ID: `claude-opus-4-8` (정확히 이 문자열, 날짜 접미사 금지)
- 웹서치 서버 도구 타입: `web_search_20260209` (Opus 4.8 지원 버전)
- 시크릿: `ANTHROPIC_API_KEY`, `SLACK_WEBHOOK_URL` 환경변수. `GEMINI_API_KEY`는 제거
- TikTok 필터 기본값: 지역=KR, 기간=7일, 정렬=인기순, 업종=전체, 상위 N=20
- 진입점 파일명은 `creative_briefing_bot.py` 유지 (GitHub Actions 명령어 안정성)
- 내부 참고용 수집만 — 재배포 안 함, 요청 간 지연 준수
- 커밋 메시지 말미: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

---

## File Structure

- Create: `briefing/__init__.py` — 빈 패키지 마커
- Create: `briefing/models.py` — `Ad` 데이터클래스
- Create: `briefing/config.py` — 상수(모델, TikTok 필터, URL)
- Create: `briefing/notify_slack.py` — `build_slack_message`, `send_to_slack`
- Create: `briefing/analyze.py` — `build_prompt`, `analyze`
- Create: `briefing/scrape_tiktok.py` — `parse_top_ads`, `scrape_tiktok`
- Create: `briefing/main.py` — `run` 오케스트레이션
- Modify: `creative_briefing_bot.py` — 진입점으로 축소(`run()` 호출)
- Create: `requirements.txt` — 의존성 고정
- Create: `tests/__init__.py`
- Create: `tests/fixtures/tiktok_top_ads.json` — 스크래퍼 파싱용 JSON 픽스처
- Create: `tests/test_models.py`, `tests/test_notify_slack.py`, `tests/test_analyze.py`, `tests/test_scrape_tiktok.py`, `tests/test_main.py`
- Modify: `.github/workflows/weekly_briefing.yml` — 의존성/시크릿/Playwright 설치 갱신

---

### Task 1: 패키지 스캐폴딩 + `Ad` 모델 + 설정

**Files:**
- Create: `briefing/__init__.py`
- Create: `briefing/models.py`
- Create: `briefing/config.py`
- Create: `tests/__init__.py`
- Create: `tests/test_models.py`
- Create: `requirements.txt`

**Interfaces:**
- Consumes: (없음)
- Produces:
  - `briefing.models.Ad` — 필드: `advertiser: str`, `industry: str`, `likes: int | None`, `ctr: float | None`, `format: str`, `caption: str`, `link: str`
  - `briefing.config` 상수: `MODEL: str`, `WEB_SEARCH_TOOL_TYPE: str`, `TIKTOK_REGION: str`, `TIKTOK_PERIOD_DAYS: int`, `TIKTOK_TOP_N: int`, `TIKTOK_TOP_ADS_URL: str`

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_models.py`

```python
from briefing.models import Ad


def test_ad_holds_all_fields():
    ad = Ad(
        advertiser="브랜드A",
        industry="뷰티",
        likes=1200,
        ctr=0.031,
        format="video",
        caption="지금 사면 50% 할인",
        link="https://ads.tiktok.com/detail/123",
    )
    assert ad.advertiser == "브랜드A"
    assert ad.likes == 1200
    assert ad.ctr == 0.031
    assert ad.link.endswith("/123")


def test_ad_allows_missing_metrics():
    ad = Ad(
        advertiser="브랜드B",
        industry="",
        likes=None,
        ctr=None,
        format="image",
        caption="",
        link="https://ads.tiktok.com/detail/456",
    )
    assert ad.likes is None
    assert ad.ctr is None
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'briefing'`

- [ ] **Step 3: 패키지/모델/설정 작성**

`briefing/__init__.py`:
```python
```
(빈 파일)

`tests/__init__.py`:
```python
```
(빈 파일)

`briefing/models.py`:
```python
from dataclasses import dataclass


@dataclass
class Ad:
    """수집된 광고 한 건. 성과 지표는 공개되지 않을 수 있어 None 허용."""

    advertiser: str
    industry: str
    likes: int | None
    ctr: float | None
    format: str
    caption: str
    link: str
```

`briefing/config.py`:
```python
# Claude 모델 (정확히 이 문자열 사용, 날짜 접미사 금지)
MODEL = "claude-opus-4-8"

# 웹서치 서버 도구 (Opus 4.8 지원 버전)
WEB_SEARCH_TOOL_TYPE = "web_search_20260209"

# TikTok Creative Center Top Ads 필터 기본값
TIKTOK_REGION = "KR"
TIKTOK_PERIOD_DAYS = 7
TIKTOK_TOP_N = 20
TIKTOK_TOP_ADS_URL = (
    "https://ads.tiktok.com/business/creativecenter/inspiration/topads/pc/en"
)
```

`requirements.txt`:
```
anthropic>=0.40
playwright>=1.44
requests>=2.31
pytest>=8.0
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_models.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: 커밋**

```bash
git add briefing/__init__.py briefing/models.py briefing/config.py tests/__init__.py tests/test_models.py requirements.txt
git commit -m "feat: add package scaffolding, Ad model, config

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Slack 메시지 포매팅 + 발송

**Files:**
- Create: `briefing/notify_slack.py`
- Create: `tests/test_notify_slack.py`

**Interfaces:**
- Consumes: `briefing.models.Ad`
- Produces:
  - `build_slack_message(brief: str, ads: list[Ad], warnings: list[str]) -> dict` — Slack Webhook용 payload(dict). `blocks` 키를 포함하며, 브리핑 텍스트 + "이번 주 인기 광고" 링크 목록 + (warnings 있으면) 경고 블록을 담는다.
  - `send_to_slack(payload: dict, webhook_url: str) -> None` — POST 발송. 200이 아니면 `RuntimeError`.

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_notify_slack.py`

```python
import json

from briefing.models import Ad
from briefing.notify_slack import build_slack_message


def _ad(name, link):
    return Ad(advertiser=name, industry="뷰티", likes=100, ctr=0.02,
             format="video", caption="cap", link=link)


def test_message_includes_brief_and_links():
    ads = [_ad("브랜드A", "https://x/1"), _ad("브랜드B", "https://x/2")]
    payload = build_slack_message("이번 주 요약", ads, warnings=[])
    text = json.dumps(payload, ensure_ascii=False)
    assert "이번 주 요약" in text
    assert "브랜드A" in text
    assert "https://x/1" in text
    assert "https://x/2" in text
    assert "blocks" in payload


def test_message_shows_warning_when_present():
    payload = build_slack_message("요약", [], warnings=["TikTok 수집 실패"])
    text = json.dumps(payload, ensure_ascii=False)
    assert "TikTok 수집 실패" in text


def test_message_handles_no_ads_without_warning():
    payload = build_slack_message("요약", [], warnings=[])
    text = json.dumps(payload, ensure_ascii=False)
    assert "요약" in text
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_notify_slack.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_slack_message'`

- [ ] **Step 3: 구현 작성** — `briefing/notify_slack.py`

```python
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
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_notify_slack.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: 커밋**

```bash
git add briefing/notify_slack.py tests/test_notify_slack.py
git commit -m "feat: add Slack Block Kit message builder and sender

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Claude 분석 (프롬프트 빌드 + 웹서치 호출)

**Files:**
- Create: `briefing/analyze.py`
- Create: `tests/test_analyze.py`

**Interfaces:**
- Consumes: `briefing.models.Ad`, `briefing.config.MODEL`, `briefing.config.WEB_SEARCH_TOOL_TYPE`
- Produces:
  - `build_prompt(ads: list[Ad]) -> str` — 수집 광고를 구조화 텍스트로 포함한 프롬프트. `ads`가 비면 "수집된 TikTok 데이터 없음 — 웹 검색으로 트렌드 파악" 지시를 포함.
  - `analyze(ads: list[Ad], api_key: str) -> str` — `anthropic.Anthropic(api_key=...)`로 `MODEL` 호출, `web_search` 도구 허용, 응답 텍스트 반환.

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_analyze.py`

```python
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
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_analyze.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_prompt'`

- [ ] **Step 3: 구현 작성** — `briefing/analyze.py`

```python
import anthropic

from briefing.config import MODEL, WEB_SEARCH_TOOL_TYPE
from briefing.models import Ad


def _format_ads(ads: list[Ad]) -> str:
    if not ads:
        return (
            "이번 주 TikTok Top Ads 자동 수집 데이터가 없습니다. "
            "web_search 도구로 '이번 주 인기 광고 / 크리에이티브 트렌드'를 "
            "직접 검색해 트렌드를 파악하세요."
        )
    rows = []
    for i, ad in enumerate(ads, 1):
        likes = "-" if ad.likes is None else f"{ad.likes:,}"
        ctr = "-" if ad.ctr is None else f"{ad.ctr:.2%}"
        rows.append(
            f"{i}. 광고주={ad.advertiser} / 업종={ad.industry} / 좋아요={likes} "
            f"/ CTR={ctr} / 포맷={ad.format} / 카피={ad.caption} / 링크={ad.link}"
        )
    return "\n".join(rows)


def build_prompt(ads: list[Ad]) -> str:
    ad_block = _format_ads(ads)
    return f"""당신은 퍼포먼스 마케터를 위한 크리에이티브 인사이트 분석가입니다.
아래는 이번 주 TikTok Creative Center의 인기 광고(Top Ads) 수집 데이터입니다.
필요하면 web_search 도구로 이번 주 광고 트렌드 기사를 추가로 찾아 보완하세요.

[수집 데이터]
{ad_block}

위 내용을 바탕으로 아래 형식으로 이번 주 크리에이티브 인사이트를 정리하세요.

형식:
1. 이번 주 주목할 트렌드 (3가지, 각 1~2줄)
2. 주목할 후킹/카피 패턴 (2~3가지, 예시 포함)
3. 포맷 트렌드 (어떤 포맷이 뜨고 있는지)
4. 우리 소재 기획에 적용할 수 있는 포인트 (1~2가지)

수집된 데이터/검색 결과에 없는 내용은 억측하지 말고 근거 기반으로만 작성하세요.
한국어로, Slack에서 읽기 좋게 간결하게 작성하세요."""


def analyze(ads: list[Ad], api_key: str) -> str:
    """Claude로 인사이트 브리핑 생성. web_search 도구 허용."""
    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        tools=[{"type": WEB_SEARCH_TOOL_TYPE, "name": "web_search"}],
        messages=[{"role": "user", "content": build_prompt(ads)}],
    )
    # 서버 도구(web_search) 사용 시 text 블록만 이어붙임
    parts = [b.text for b in response.content if b.type == "text"]
    return "\n".join(p for p in parts if p).strip()
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_analyze.py -v`
Expected: PASS (2 passed)

참고: `analyze()` 자체는 실제 API 키가 필요하므로 단위 테스트하지 않는다(프롬프트 빌드만 검증). SDK가 429/5xx를 자동 백오프 재시도한다.

- [ ] **Step 5: 커밋**

```bash
git add briefing/analyze.py tests/test_analyze.py
git commit -m "feat: add Claude analysis with web_search tool

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: TikTok Top Ads 스크래핑 (JSON 파싱 + Playwright 수집)

**Files:**
- Create: `briefing/scrape_tiktok.py`
- Create: `tests/test_scrape_tiktok.py`
- Create: `tests/fixtures/tiktok_top_ads.json`

**Interfaces:**
- Consumes: `briefing.models.Ad`, `briefing.config` (URL, REGION, TOP_N)
- Produces:
  - `parse_top_ads(payload: dict, top_n: int) -> list[Ad]` — TikTok 내부 API 응답(JSON dict)에서 상위 `top_n`개 광고를 `Ad`로 변환. 필드 누락에 방어적(`.get`).
  - `scrape_tiktok() -> list[Ad]` — Playwright로 Top Ads 페이지를 열고, 내부 API 응답(JSON)을 가로채 `parse_top_ads`에 넘긴다. 어떤 실패든 예외를 잡아 `[]` 반환.

> **구현 주의 (실측 필요):** TikTok Creative Center는 페이지 로드 시 내부 API
> (`.../creative_radar_api/.../top_ads/...`)를 XHR로 호출해 JSON을 받는다.
> 정확한 URL 경로와 JSON 필드명은 **구현 시점에 실제 응답을 한 번 캡처해 확인**해야
> 한다. 아래 스키마는 가정이며, 실제 응답을 `tests/fixtures/tiktok_top_ads.json`으로
> 저장한 뒤 필드 매핑을 맞춘다. 파서는 `.get()` 기반이라 스키마가 조금 달라도
> 크래시 없이 degrade 한다.

- [ ] **Step 1: JSON 픽스처 작성** — `tests/fixtures/tiktok_top_ads.json`

(가정 스키마. 구현 시 실제 응답으로 교체)
```json
{
  "data": {
    "materials": [
      {
        "brand_name": "브랜드A",
        "industry_label": "뷰티",
        "like": 1234,
        "ctr": 0.031,
        "video_url": "https://v/1",
        "ad_title": "여름 세일 지금",
        "id": "aaa111"
      },
      {
        "brand_name": "브랜드B",
        "industry_label": "패션",
        "like": 980,
        "ctr": null,
        "ad_title": "가을 신상",
        "id": "bbb222"
      }
    ]
  }
}
```

- [ ] **Step 2: 실패하는 테스트 작성** — `tests/test_scrape_tiktok.py`

```python
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
```

- [ ] **Step 3: 테스트 실패 확인**

Run: `python -m pytest tests/test_scrape_tiktok.py -v`
Expected: FAIL — `ImportError: cannot import name 'parse_top_ads'`

- [ ] **Step 4: 구현 작성** — `briefing/scrape_tiktok.py`

```python
from briefing.config import (
    TIKTOK_REGION,
    TIKTOK_TOP_ADS_URL,
    TIKTOK_TOP_N,
)
from briefing.models import Ad

# TikTok 상세 링크 베이스 (id를 붙여 완성)
_DETAIL_BASE = "https://ads.tiktok.com/business/creativecenter/inspiration/topads/detail/"


def parse_top_ads(payload: dict, top_n: int) -> list[Ad]:
    """TikTok 내부 API 응답(JSON)에서 상위 top_n개 광고를 Ad로 변환.

    실제 필드명은 구현 시 캡처한 응답에 맞춰 조정한다. 누락에 방어적.
    """
    materials = (payload or {}).get("data", {}).get("materials", []) or []
    ads: list[Ad] = []
    for m in materials[:top_n]:
        ad_id = str(m.get("id", ""))
        ads.append(
            Ad(
                advertiser=m.get("brand_name") or "",
                industry=m.get("industry_label") or "",
                likes=m.get("like"),
                ctr=m.get("ctr"),
                format="video" if m.get("video_url") else "image",
                caption=m.get("ad_title") or "",
                link=_DETAIL_BASE + ad_id if ad_id else TIKTOK_TOP_ADS_URL,
            )
        )
    return ads


def scrape_tiktok() -> list[Ad]:
    """Playwright로 Top Ads 페이지의 내부 API JSON을 가로채 파싱.

    어떤 실패든 잡아서 빈 리스트를 반환한다(봇은 계속 진행).
    """
    captured: dict = {}
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
                )
            )

            def on_response(response):
                # 내부 top_ads API 응답만 캡처
                if "top_ads" in response.url and "api" in response.url:
                    try:
                        captured.update(response.json())
                    except Exception:
                        pass

            page.on("response", on_response)
            page.goto(
                f"{TIKTOK_TOP_ADS_URL}?region={TIKTOK_REGION}",
                wait_until="networkidle",
                timeout=60000,
            )
            page.wait_for_timeout(3000)  # 지연 후 XHR 완료 대기
            browser.close()
    except Exception as e:  # noqa: BLE001 - 부분 실패 허용
        print(f"[TikTok 스크래핑 실패: {e}]")
        return []

    return parse_top_ads(captured, TIKTOK_TOP_N)
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `python -m pytest tests/test_scrape_tiktok.py -v`
Expected: PASS (4 passed)

- [ ] **Step 6: (구현 시점) 실제 응답으로 픽스처/필드 검증**

로컬에서 `playwright install chromium` 후 아래를 실행해 실제 응답을 확인하고,
`captured`의 실제 키에 맞춰 `parse_top_ads`의 `.get(...)` 필드명과
`tests/fixtures/tiktok_top_ads.json`을 갱신한다. 그런 다음 Step 5 테스트를 다시 통과시킨다.

```bash
python -c "from briefing.scrape_tiktok import scrape_tiktok; ads=scrape_tiktok(); print(len(ads)); [print(a) for a in ads[:3]]"
```
Expected: 광고 몇 건이 출력됨. 0건이면 `top_ads` API URL 매칭 조건(`on_response`)을
실제 응답 URL에 맞춰 조정한다.

- [ ] **Step 7: 커밋**

```bash
git add briefing/scrape_tiktok.py tests/test_scrape_tiktok.py tests/fixtures/tiktok_top_ads.json
git commit -m "feat: add TikTok Top Ads scraper (Playwright + JSON parse)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: 오케스트레이션 + 진입점 + 워크플로우

**Files:**
- Create: `briefing/main.py`
- Modify: `creative_briefing_bot.py`
- Create: `tests/test_main.py`
- Modify: `.github/workflows/weekly_briefing.yml`

**Interfaces:**
- Consumes: `scrape_tiktok`, `analyze`, `build_slack_message`, `send_to_slack`
- Produces: `briefing.main.run() -> None`

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_main.py`

```python
import briefing.main as main
from briefing.models import Ad


def _ad():
    return Ad(advertiser="A", industry="뷰티", likes=1, ctr=0.01,
             format="video", caption="c", link="https://x/1")


def test_run_happy_path(monkeypatch):
    sent = {}
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hook")
    monkeypatch.setattr(main, "scrape_tiktok", lambda: [_ad()])
    monkeypatch.setattr(main, "analyze", lambda ads, api_key: "요약")
    monkeypatch.setattr(main, "send_to_slack", lambda payload, url: sent.update(payload=payload))

    main.run()

    text = str(sent["payload"])
    assert "요약" in text
    assert "A" in text


def test_run_continues_when_scrape_fails(monkeypatch):
    sent = {}
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hook")
    monkeypatch.setattr(main, "scrape_tiktok", lambda: [])  # 수집 실패 → 빈 리스트
    monkeypatch.setattr(main, "analyze", lambda ads, api_key: "웹서치 기반 요약")
    monkeypatch.setattr(main, "send_to_slack", lambda payload, url: sent.update(payload=payload))

    main.run()

    text = str(sent["payload"])
    assert "웹서치 기반 요약" in text
    assert "수집" in text  # 경고 문구 포함
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_main.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'briefing.main'`

- [ ] **Step 3: 구현 작성** — `briefing/main.py`

```python
import os
import sys

from briefing.analyze import analyze
from briefing.notify_slack import build_slack_message, send_to_slack
from briefing.scrape_tiktok import scrape_tiktok


def run() -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if not api_key or not webhook_url:
        print("❌ ANTHROPIC_API_KEY / SLACK_WEBHOOK_URL 환경변수 필요")
        sys.exit(1)

    warnings: list[str] = []

    print("🔍 TikTok Top Ads 수집 중...")
    ads = scrape_tiktok()
    if not ads:
        warnings.append("TikTok 인기 광고 수집 실패 — 웹 검색 기반으로 작성됨")

    print("🤖 Claude 분석 중...")
    brief = analyze(ads, api_key)  # 실패 시 예외 → 비정상 종료

    print("📨 Slack 발송 중...")
    payload = build_slack_message(brief, ads, warnings)
    send_to_slack(payload, webhook_url)  # 실패 시 RuntimeError → 비정상 종료

    print("✅ 완료!")
```

- [ ] **Step 4: 진입점 축소** — `creative_briefing_bot.py` (전체 내용 교체)

```python
"""주간 크리에이티브 인사이트 브리핑 봇 (진입점).

실제 로직은 briefing 패키지에 있다. GitHub Actions가 이 파일을 실행한다.
"""

from briefing.main import run

if __name__ == "__main__":
    run()
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `python -m pytest tests/test_main.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: 전체 테스트 통과 확인**

Run: `python -m pytest -v`
Expected: 모든 테스트 PASS

- [ ] **Step 7: 워크플로우 갱신** — `.github/workflows/weekly_briefing.yml` (전체 교체)

```yaml
name: 주간 크리에이티브 인사이트 브리핑

on:
  schedule:
    - cron: '0 0 * * 1'
  workflow_dispatch:

jobs:
  briefing:
    runs-on: ubuntu-latest

    steps:
      - name: 코드 체크아웃
        uses: actions/checkout@v4

      - name: Python 세팅
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: 패키지 설치
        run: |
          pip install -r requirements.txt
          python -m playwright install --with-deps chromium

      - name: 브리핑 봇 실행
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
        run: python creative_briefing_bot.py
```

- [ ] **Step 8: 커밋**

```bash
git add briefing/main.py creative_briefing_bot.py tests/test_main.py .github/workflows/weekly_briefing.yml
git commit -m "feat: wire orchestration, entrypoint, and CI workflow (Gemini→Claude)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## 배포 후 수동 확인 (구현 완료 후)

1. GitHub 저장소 Settings → Secrets에 `ANTHROPIC_API_KEY` 추가, `GEMINI_API_KEY` 제거
2. Actions 탭 → "주간 크리에이티브 인사이트 브리핑" → `Run workflow`(workflow_dispatch)로 수동 실행
3. Slack 채널에 브리핑이 도착하는지, 인기 광고 링크가 열리는지 확인
4. TikTok 수집이 0건이면 Task 4 Step 6대로 `on_response` URL 매칭을 실제 응답에 맞춰 조정
```
