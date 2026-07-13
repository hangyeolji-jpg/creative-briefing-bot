# 크리에이티브 브리핑 아카이브 웹 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 봇이 매주 생성하는 브리핑을 git 저장소에 JSON+썸네일로 영속화하고, Vercel에 배포되는 비공개(팀 전용) 정적 웹 대시보드에서 날짜별로 열람한다.

**Architecture:** 봇(Python)이 Slack 발송 후 `web/data/`에 브리핑 JSON·인덱스·썸네일을 쓰고 GitHub Action이 이를 커밋·푸시한다. 같은 repo의 `web/`를 루트로 하는 Vercel 정적 배포가 그 데이터를 vanilla JS로 렌더하며, Edge Middleware가 HTTP Basic Auth로 비공개를 보장한다.

**Tech Stack:** Python 3.11 (dataclass, pytest, urllib), 정적 HTML/CSS/vanilla JS, Vercel Edge Middleware, GitHub Actions.

## Global Constraints

- Claude 모델 문자열은 정확히 `claude-opus-4-8` (날짜 접미사 금지) — 기존 config 유지, 이 플랜에서 변경 없음.
- 웹은 **빌드 도구·프레임워크 없음.** 순수 HTML/CSS/JS.
- 저장소: 기존 `creative-briefing-bot` 안 `web/` 하위 폴더.
- 아카이브 저장 실패는 **비치명적** — Slack 발송이 이미 끝났으므로 전체 실행을 실패시키지 않는다.
- 썸네일은 만료되는 원본 URL을 저장하지 않고 **다운로드해 로컬 경로**로 저장. 다운로드 실패 시 `null`.
- 날짜 형식은 KST 기준 `YYYY-MM-DD`.
- JSON 파일은 `ensure_ascii=False, indent=2`, UTF-8로 기록.

---

### Task 1: `Ad.thumbnail` 필드 + cover 캡처

**Files:**
- Modify: `briefing/models.py`
- Modify: `briefing/scrape_tiktok.py` (`parse_top_ads`)
- Test: `tests/test_scrape_tiktok.py` (추가)

**Interfaces:**
- Consumes: 기존 `parse_top_ads(payload, top_n, industry_map=None) -> list[Ad]`, 픽스처 `tests/fixtures/tiktok_top_ads.json`(첫 광고에 `video_info.cover = "https://p16/cover1.jpg"`, 둘째 광고엔 `video_info` 없음).
- Produces: `Ad`에 `thumbnail: str | None = None` 필드. `parse_top_ads`가 `video_info.cover`를 `thumbnail`으로 채움.

- [ ] **Step 1: Write the failing test**

`tests/test_scrape_tiktok.py` 끝에 추가:

```python
def test_parse_captures_thumbnail_from_video_info():
    ads = parse_top_ads(_payload(), top_n=20, industry_map=_industry_map())
    assert ads[0].thumbnail == "https://p16/cover1.jpg"  # video_info.cover
    assert ads[1].thumbnail is None  # video_info 없음
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_scrape_tiktok.py::test_parse_captures_thumbnail_from_video_info -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'thumbnail'` 또는 `AttributeError: 'Ad' object has no attribute 'thumbnail'`.

- [ ] **Step 3: Add the field to `Ad`**

`briefing/models.py` 의 `Ad`를 다음으로 교체:

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
    thumbnail: str | None = None
```

- [ ] **Step 4: Capture cover in `parse_top_ads`**

`briefing/scrape_tiktok.py` 의 `parse_top_ads` 루프 본문을 다음으로 교체 (video_info를 한 번만 읽어 format과 thumbnail 모두에 사용):

```python
    industry_map = industry_map or {}
    materials = (payload or {}).get("data", {}).get("materials", []) or []
    ads: list[Ad] = []
    for m in materials[:top_n]:
        ad_id = str(m.get("id", ""))
        industry_key = m.get("industry_key") or ""
        video_info = m.get("video_info") or {}
        ads.append(
            Ad(
                advertiser=m.get("brand_name") or "",
                industry=industry_map.get(industry_key, industry_key),
                likes=m.get("like"),
                ctr=m.get("ctr"),
                format="video" if video_info else "image",
                caption=m.get("ad_title") or "",
                link=_detail_link(ad_id),
                thumbnail=(video_info.get("cover") if isinstance(video_info, dict) else None),
            )
        )
    return ads
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_scrape_tiktok.py -v`
Expected: PASS (기존 + 신규 테스트 모두).

- [ ] **Step 6: Commit**

```bash
git add briefing/models.py briefing/scrape_tiktok.py tests/test_scrape_tiktok.py
git commit -m "feat: capture TikTok cover as Ad.thumbnail"
```

---

### Task 2: `save_briefing` — 아카이브 영속화

**Files:**
- Create: `briefing/save_briefing.py`
- Test: `tests/test_save_briefing.py`

**Interfaces:**
- Consumes: `Ad`(thumbnail 포함, Task 1).
- Produces:
  - `save_briefing(date: str, brief: str, ads: list[Ad], warnings: list[str], data_dir: str | Path, *, generated_at: str | None = None, fetch=_default_fetch) -> dict`
    — `web/data/briefings/<date>.json` 기록, `web/data/index.json` upsert, 썸네일을 `web/data/thumbs/<date>/<NN>.jpg`로 다운로드. 반환 record dict.
  - `fetch(url: str, dest: Path) -> bool` 훅(테스트 주입용). 기본 `_default_fetch`.

- [ ] **Step 1: Write the failing tests**

`tests/test_save_briefing.py` 생성:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_save_briefing.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'briefing.save_briefing'`.

- [ ] **Step 3: Implement `save_briefing`**

`briefing/save_briefing.py` 생성:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_save_briefing.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add briefing/save_briefing.py tests/test_save_briefing.py
git commit -m "feat: add save_briefing archive persistence"
```

---

### Task 3: `main.py` — 발송 후 아카이브 저장(비치명적)

**Files:**
- Modify: `briefing/main.py`
- Test: `tests/test_main.py`

**Interfaces:**
- Consumes: `save_briefing(...)`(Task 2), 기존 `scrape_tiktok`/`analyze`/`build_slack_message`/`send_to_slack`.
- Produces: `run()`이 Slack 발송 후 `save_briefing(date, brief, ads, warnings, "web/data")`를 호출하되 예외를 삼켜 비치명적으로 처리. `main.save_briefing`으로 참조되어 테스트에서 mock 가능.

- [ ] **Step 1: Update existing tests + add new ones**

`tests/test_main.py`의 세 기존 테스트에서 실제 파일 I/O를 막기 위해 `save_briefing`을 mock하고, 두 신규 테스트를 추가한다. 파일 전체를 다음으로 교체:

```python
import pytest

import briefing.main as main
from briefing.models import Ad


def _ad():
    return Ad(advertiser="A", industry="뷰티", likes=1, ctr=0.01,
             format="video", caption="c", link="https://x/1")


def _env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hook")


def test_run_happy_path(monkeypatch):
    sent = {}
    _env(monkeypatch)
    monkeypatch.setattr(main, "scrape_tiktok", lambda: [_ad()])
    monkeypatch.setattr(main, "analyze", lambda ads, api_key: "요약")
    monkeypatch.setattr(main, "send_to_slack", lambda payload, url: sent.update(payload=payload))
    monkeypatch.setattr(main, "save_briefing", lambda *a, **k: None)

    main.run()

    text = str(sent["payload"])
    assert "요약" in text
    assert "A" in text


def test_run_exits_when_env_vars_missing(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    with pytest.raises(SystemExit):
        main.run()


def test_run_continues_when_scrape_fails(monkeypatch):
    sent = {}
    _env(monkeypatch)
    monkeypatch.setattr(main, "scrape_tiktok", lambda: [])
    monkeypatch.setattr(main, "analyze", lambda ads, api_key: "웹서치 기반 요약")
    monkeypatch.setattr(main, "send_to_slack", lambda payload, url: sent.update(payload=payload))
    monkeypatch.setattr(main, "save_briefing", lambda *a, **k: None)

    main.run()

    text = str(sent["payload"])
    assert "웹서치 기반 요약" in text
    assert "수집" in text


def test_run_saves_archive(monkeypatch):
    calls = {}
    _env(monkeypatch)
    monkeypatch.setattr(main, "scrape_tiktok", lambda: [_ad()])
    monkeypatch.setattr(main, "analyze", lambda ads, api_key: "요약")
    monkeypatch.setattr(main, "send_to_slack", lambda payload, url: None)
    monkeypatch.setattr(main, "save_briefing",
                        lambda *a, **k: calls.update(saved=True, args=a))

    main.run()

    assert calls.get("saved") is True
    # 위치 인자: date, brief, ads, warnings, data_dir
    assert calls["args"][1] == "요약"
    assert calls["args"][4] == "web/data"


def test_run_archive_failure_is_non_fatal(monkeypatch):
    _env(monkeypatch)
    monkeypatch.setattr(main, "scrape_tiktok", lambda: [_ad()])
    monkeypatch.setattr(main, "analyze", lambda ads, api_key: "요약")
    monkeypatch.setattr(main, "send_to_slack", lambda payload, url: None)

    def _boom(*a, **k):
        raise IOError("disk full")

    monkeypatch.setattr(main, "save_briefing", _boom)

    main.run()  # 예외가 전파되면 안 됨 (테스트가 실패로 잡음)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_main.py -v`
Expected: FAIL — `test_run_saves_archive`가 `AttributeError: module 'briefing.main' has no attribute 'save_briefing'` 로 실패.

- [ ] **Step 3: Wire save_briefing into `main.run`**

`briefing/main.py` 전체를 다음으로 교체:

```python
import os
import sys
from datetime import datetime, timedelta, timezone

from briefing.analyze import analyze
from briefing.notify_slack import build_slack_message, send_to_slack
from briefing.save_briefing import save_briefing
from briefing.scrape_tiktok import scrape_tiktok

_KST = timezone(timedelta(hours=9))
_DATA_DIR = "web/data"


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

    date = datetime.now(_KST).strftime("%Y-%m-%d")
    try:
        save_briefing(date, brief, ads, warnings, _DATA_DIR)
        print("🗄️ 아카이브 저장 완료")
    except Exception as e:  # noqa: BLE001 - 아카이브 실패는 비치명적
        print(f"[아카이브 저장 실패(비치명적): {e}]")

    print("✅ 완료!")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_main.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Run full suite**

Run: `python -m pytest -q`
Expected: PASS (전체).

- [ ] **Step 6: Commit**

```bash
git add briefing/main.py tests/test_main.py
git commit -m "feat: persist archive after Slack send (non-fatal)"
```

---

### Task 4: GitHub Action — `web/data` 커밋 & 푸시

**Files:**
- Modify: `.github/workflows/weekly_briefing.yml`
- Create: `web/data/index.json` (초기 빈 상태)
- Create: `web/data/.gitkeep` 대체 — briefings/thumbs 디렉터리 보존용

**Interfaces:**
- Consumes: 봇 실행이 `web/data/`에 파일 생성(Task 2·3).
- Produces: 워크플로가 변경분을 커밋·푸시. 웹이 읽을 초기 `index.json` 존재.

- [ ] **Step 1: Create initial data files**

`web/data/index.json` 생성:

```json
{
  "briefings": []
}
```

`web/data/briefings/.gitkeep` 생성 (빈 파일):

```
```

`web/data/thumbs/.gitkeep` 생성 (빈 파일):

```
```

- [ ] **Step 2: Update the workflow**

`.github/workflows/weekly_briefing.yml` 전체를 다음으로 교체 (permissions 추가 + 커밋 스텝):

```yaml
name: 주간 크리에이티브 인사이트 브리핑

on:
  schedule:
    - cron: '0 0 * * 1'
  workflow_dispatch:

permissions:
  contents: write

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

      - name: 아카이브 커밋 & 푸시
        run: |
          git config user.name "briefing-bot"
          git config user.email "briefing-bot@users.noreply.github.com"
          git add web/data
          if git diff --cached --quiet; then
            echo "변경 없음 — skip"
          else
            git commit -m "chore: archive $(date -u +%F) briefing"
            git push
          fi
```

- [ ] **Step 3: Verify workflow YAML parses**

Run: `python -c "import yaml, sys; yaml.safe_load(open('.github/workflows/weekly_briefing.yml', encoding='utf-8')); print('YAML OK')"`
Expected: `YAML OK` (yaml 미설치 시 `pip install pyyaml` 후 재실행).

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/weekly_briefing.yml web/data/index.json web/data/briefings/.gitkeep web/data/thumbs/.gitkeep
git commit -m "ci: commit archive data after briefing run"
```

---

### Task 5: 정적 웹 대시보드 (index.html + styles.css + app.js)

**Files:**
- Create: `web/index.html`
- Create: `web/styles.css`
- Create: `web/app.js`

**Interfaces:**
- Consumes: `web/data/index.json`(`{briefings:[{date,ad_count,headline}]}`), `web/data/briefings/<date>.json`(record: `{date,generated_at,brief,warnings,ads:[{advertiser,industry,likes,ctr,format,caption,link,thumbnail}]}`), 로컬 썸네일 `web/data/thumbs/...`.
- Produces: 브라우저에서 목록→상세를 렌더하는 정적 페이지.

- [ ] **Step 1: Create `web/index.html`**

```html
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>크리에이티브 브리핑 아카이브</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <header class="site-header">
    <h1>크리에이티브 브리핑 아카이브</h1>
  </header>
  <main class="layout">
    <aside class="sidebar">
      <nav id="brief-list" class="brief-list" aria-label="브리핑 목록"></nav>
    </aside>
    <section id="detail" class="detail" aria-live="polite"></section>
  </main>
  <script src="app.js"></script>
</body>
</html>
```

- [ ] **Step 2: Create `web/styles.css`** (Apple 스타일 가이드: 단일 블루 #0066cc, 17px 본문, 무그라디언트, 절제된 그림자)

```css
:root {
  --blue: #0066cc;
  --ink: #1d1d1f;
  --muted: #6e6e73;
  --line: #e5e5ea;
  --canvas: #faf9f6;
  --card: #ffffff;
  --radius: 14px;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro", "Inter",
    "Apple SD Gothic Neo", "Malgun Gothic", sans-serif;
  font-size: 17px;
  line-height: 1.6;
  color: var(--ink);
  background: var(--canvas);
}

.site-header {
  padding: 22px 32px;
  border-bottom: 1px solid var(--line);
  background: var(--card);
}
.site-header h1 { margin: 0; font-size: 21px; font-weight: 600; }

.layout {
  display: grid;
  grid-template-columns: 300px 1fr;
  gap: 0;
  min-height: calc(100vh - 66px);
}

.sidebar {
  border-right: 1px solid var(--line);
  background: var(--card);
  overflow-y: auto;
}
.brief-list { display: flex; flex-direction: column; }
.brief-list a {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 14px 20px;
  border-bottom: 1px solid var(--line);
  text-decoration: none;
  color: var(--ink);
}
.brief-list a:hover { background: #f5f5f7; }
.brief-list a.active { background: #eef4fd; box-shadow: inset 3px 0 0 var(--blue); }
.li-date { font-weight: 600; font-size: 15px; }
.li-headline { font-size: 14px; color: var(--muted);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.li-count { font-size: 12px; color: var(--blue); }

.detail { padding: 32px 40px; max-width: 1100px; }
.detail-date { margin: 0 0 16px; font-size: 28px; font-weight: 700; }
.brief-text { font-size: 17px; }
.brief-text h3 { font-size: 19px; margin: 24px 0 8px; }
.brief-text p { margin: 0 0 12px; }
.warnings {
  background: #fff8e6; border: 1px solid #f0e0a8; color: #8a6d00;
  padding: 10px 14px; border-radius: 10px; font-size: 14px; margin-bottom: 18px;
}
.ads-heading { font-size: 20px; margin: 32px 0 14px; }

.ad-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 18px;
}
.ad-card {
  display: flex; flex-direction: column;
  background: var(--card); border: 1px solid var(--line);
  border-radius: var(--radius); overflow: hidden;
  text-decoration: none; color: var(--ink);
  transition: box-shadow .15s ease;
}
.ad-card:hover { box-shadow: 0 8px 24px rgba(0,0,0,.08); }
.ad-thumb { width: 100%; aspect-ratio: 9 / 16; object-fit: cover;
  background: #f0f0f2; display: block; }
.ad-thumb--empty { display: flex; align-items: center; justify-content: center;
  font-size: 34px; color: #c7c7cc; }
.ad-body { padding: 12px 14px; display: flex; flex-direction: column; gap: 6px; }
.ad-top { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; }
.ad-advertiser { font-weight: 600; font-size: 15px; }
.ad-industry { font-size: 12px; color: var(--muted); white-space: nowrap; }
.ad-caption { margin: 0; font-size: 14px; color: #3a3a3c;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden; }
.ad-metrics { display: flex; gap: 14px; font-size: 13px; color: var(--blue); }

.muted { color: var(--muted); }
.empty { padding: 60px 0; text-align: center; }
.empty h2 { font-weight: 600; }

@media (max-width: 720px) {
  .layout { grid-template-columns: 1fr; }
  .sidebar { border-right: none; border-bottom: 1px solid var(--line); max-height: 220px; }
  .detail { padding: 24px 20px; }
}
```

- [ ] **Step 3: Create `web/app.js`**

```javascript
const listEl = document.getElementById("brief-list");
const detailEl = document.getElementById("detail");

async function loadJSON(path) {
  const res = await fetch(path, { cache: "no-store" });
  if (!res.ok) throw new Error(`${path} → ${res.status}`);
  return res.json();
}

function fmtPct(v) { return v == null ? "–" : `${Math.round(v * 100)}%`; }
function fmtNum(v) { return v == null ? "–" : v.toLocaleString(); }
function esc(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

// 아주 간단한 마크다운 → HTML (제목/굵게/문단만). 입력은 먼저 이스케이프.
function miniMarkdown(md) {
  return esc(md)
    .replace(/^#{1,6}\s?(.*)$/gm, "<h3>$1</h3>")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .split(/\n{2,}/)
    .map((block) => (block.startsWith("<h3>") ? block : `<p>${block.replace(/\n/g, "<br>")}</p>`))
    .join("");
}

function adCard(ad) {
  const thumb = ad.thumbnail
    ? `<img class="ad-thumb" src="data/${esc(ad.thumbnail)}" alt="" loading="lazy">`
    : `<div class="ad-thumb ad-thumb--empty">${ad.format === "video" ? "▶" : "🖼"}</div>`;
  return `
    <a class="ad-card" href="${esc(ad.link)}" target="_blank" rel="noopener">
      ${thumb}
      <div class="ad-body">
        <div class="ad-top">
          <span class="ad-advertiser">${esc(ad.advertiser) || "(광고주 미상)"}</span>
          <span class="ad-industry">${esc(ad.industry)}</span>
        </div>
        <p class="ad-caption">${esc(ad.caption)}</p>
        <div class="ad-metrics">
          <span>♥ ${fmtNum(ad.likes)}</span>
          <span>CTR ${fmtPct(ad.ctr)}</span>
        </div>
      </div>
    </a>`;
}

async function showBriefing(date) {
  detailEl.innerHTML = `<p class="muted">불러오는 중…</p>`;
  listEl.querySelectorAll("a").forEach((a) =>
    a.classList.toggle("active", a.dataset.date === date));
  try {
    const b = await loadJSON(`data/briefings/${date}.json`);
    const cards = (b.ads || []).map(adCard).join("");
    const warn = (b.warnings || []).length
      ? `<div class="warnings">${b.warnings.map((w) => `⚠️ ${esc(w)}`).join("<br>")}</div>`
      : "";
    detailEl.innerHTML = `
      <h2 class="detail-date">${esc(b.date)}</h2>
      ${warn}
      <div class="brief-text">${miniMarkdown(b.brief)}</div>
      <h3 class="ads-heading">이번 주 인기 광고</h3>
      <div class="ad-grid">${cards || '<p class="muted">수집된 광고가 없습니다.</p>'}</div>`;
  } catch (e) {
    detailEl.innerHTML = `<p class="muted">이 브리핑을 불러오지 못했습니다 (${esc(e.message)}).</p>`;
  }
}

async function init() {
  try {
    const index = await loadJSON("data/index.json");
    const briefings = index.briefings || [];
    if (!briefings.length) {
      detailEl.innerHTML = `<div class="empty"><h2>아직 브리핑이 없습니다</h2>
        <p class="muted">봇이 첫 브리핑을 생성하면 여기에 표시됩니다.</p></div>`;
      return;
    }
    listEl.innerHTML = briefings.map((b) => `
      <a href="#${esc(b.date)}" data-date="${esc(b.date)}">
        <span class="li-date">${esc(b.date)}</span>
        <span class="li-headline">${esc(b.headline)}</span>
        <span class="li-count">${esc(b.ad_count)}개</span>
      </a>`).join("");
    listEl.querySelectorAll("a").forEach((a) =>
      a.addEventListener("click", (ev) => { ev.preventDefault(); showBriefing(a.dataset.date); }));
    showBriefing(location.hash.slice(1) || briefings[0].date);
  } catch (e) {
    detailEl.innerHTML = `<p class="muted">아카이브를 불러오지 못했습니다 (${esc(e.message)}).</p>`;
  }
}

init();
```

- [ ] **Step 4: Generate sample data and verify locally**

임시 샘플 브리핑을 만들어 렌더를 육안 확인한다 (썸네일 다운로드는 끔):

Run:
```bash
python -c "from briefing.models import Ad; from briefing.save_briefing import save_briefing; save_briefing('2026-07-13', '# 이번 주 트렌드\n**후킹**: 첫 3초 승부.\n\n## 포맷\n세로 영상 우세.', [Ad('브랜드A','Women\'s Clothing',111806,0.30,'video','첫 3초에 훅을 거는 UGC 스타일','https://ads.tiktok.com/business/creativecenter/topads/1/pc/en', None)], ['TikTok 수집 실패 — 웹 검색 기반'], 'web/data', generated_at='2026-07-13T00:00:00Z', fetch=lambda u,d: False)"
python -m http.server 8000 --directory web
```
브라우저에서 `http://localhost:8000` 접속.
Expected: 좌측에 `2026-07-13` 항목, 클릭 시 우측에 트렌드 본문 + 경고 배지 + 광고 카드 1개(썸네일 없어 ▶ 플레이스홀더, 광고주/업종/♥111,806/CTR 30%) 표시. `http.server`는 `Ctrl+C`로 종료.

- [ ] **Step 5: Reset sample data**

샘플을 지워 초기 빈 상태로 되돌린다 (실제 봇 데이터만 커밋되도록):

Run:
```bash
git checkout web/data/index.json
rm -rf web/data/briefings/2026-07-13.json web/data/thumbs/2026-07-13
```
Run: `git status --short`
Expected: `web/index.html`, `web/styles.css`, `web/app.js`만 신규(Untracked)로 남고 `web/data`는 변경 없음.

- [ ] **Step 6: Commit**

```bash
git add web/index.html web/styles.css web/app.js
git commit -m "feat: static archive dashboard (list + detail + ad cards)"
```

---

### Task 6: Vercel Edge Middleware Basic Auth + 배포 설정

**Files:**
- Create: `web/middleware.js`
- Create: `web/vercel.json`
- Create: `web/README.md` (배포 절차)

**Interfaces:**
- Consumes: Vercel 환경변수 `SITE_PASSWORD`.
- Produces: 모든 요청에 HTTP Basic Auth를 강제하는 Edge Middleware + 배포 문서.

- [ ] **Step 1: Create `web/middleware.js`**

```javascript
// Vercel Edge Middleware — 모든 요청에 HTTP Basic Auth 강제.
// 환경변수 SITE_PASSWORD 와 일치하는 비밀번호만 통과.
export const config = { matcher: "/((?!favicon.ico).*)" };

export default function middleware(request) {
  const expected = process.env.SITE_PASSWORD || "";
  // 비번 미설정 시 잠그지 않음(로컬/미설정 환경 편의). 운영에선 반드시 설정.
  if (!expected) return;

  const header = request.headers.get("authorization") || "";
  if (header.startsWith("Basic ")) {
    try {
      const decoded = atob(header.slice(6));
      const password = decoded.slice(decoded.indexOf(":") + 1);
      if (password === expected) return; // 통과
    } catch (_e) {
      // 디코드 실패 → 아래에서 401
    }
  }
  return new Response("인증이 필요합니다.", {
    status: 401,
    headers: { "WWW-Authenticate": 'Basic realm="briefing-archive"' },
  });
}
```

- [ ] **Step 2: Create `web/vercel.json`**

```json
{
  "cleanUrls": true
}
```

- [ ] **Step 3: Create `web/README.md`**

```markdown
# 크리에이티브 브리핑 아카이브 (웹)

봇이 `web/data/`에 커밋한 주간 브리핑을 열람하는 정적 대시보드.

## 로컬 실행
```bash
python -m http.server 8000 --directory web
# http://localhost:8000
```
(로컬에서는 `SITE_PASSWORD` 미설정이라 인증 없이 열림.)

## Vercel 배포 (최초 1회)
1. Vercel에서 New Project → 이 GitHub 저장소 선택.
2. **Root Directory = `web`** 로 지정.
3. Framework Preset = **Other** (빌드 없음).
4. Environment Variables 에 `SITE_PASSWORD` = 팀 공용 비밀번호 추가.
5. Deploy.

이후 봇이 매주 `web/data`를 push하면 Vercel이 자동 재배포한다.
접속 시 브라우저 Basic Auth 창에서 아이디는 아무 값, 비번은 `SITE_PASSWORD`.
```

- [ ] **Step 4: Verify middleware + vercel.json parse**

Run: `node --check web/middleware.js && python -c "import json; json.load(open('web/vercel.json', encoding='utf-8')); print('JSON OK')"`
Expected: `JSON OK` (에러 없이). node 미설치 시 middleware.js 문법 검사는 건너뛰고 육안 확인.

- [ ] **Step 5: Commit**

```bash
git add web/middleware.js web/vercel.json web/README.md
git commit -m "feat: Basic Auth middleware + Vercel deploy config"
```

---

## 배포 (수동, 코드 밖 단계)

플랜 구현 후 사용자가 Vercel 대시보드에서 1회 수행 (web/README.md 참고):
Root Directory=`web`, `SITE_PASSWORD` 환경변수 설정, Deploy. 이후 자동 재배포.

## Self-Review

**Spec coverage:**
- 브리핑 영속화(JSON+index+썸네일) → Task 2 ✓
- Ad.thumbnail(cover 재활용) → Task 1 ✓
- 발송 후 저장, 비치명적 → Task 3 ✓
- Action commit&push → Task 4 ✓
- 정적 대시보드(목록/상세/카드, Apple 스타일) → Task 5 ✓
- 비공개 Basic Auth(Edge Middleware, SITE_PASSWORD) → Task 6 ✓
- 데이터 계약(index.json, briefing json 스키마) → Task 2 산출 + Task 5 소비 ✓
- 에러 처리(썸네일 실패 null, 개별 로드 실패, 빈 아카이브) → Task 2/5 ✓
- Vercel Root=web, 환경변수 → Task 6 README ✓

**Placeholder scan:** 모든 스텝에 실제 코드/명령 포함. TODO/TBD 없음.

**Type consistency:** `save_briefing(date, brief, ads, warnings, data_dir, *, generated_at, fetch)` 시그니처가 Task 2 정의 = Task 3 호출(위치 인자 5개 + data_dir="web/data")과 일치. record/index JSON 키(date, generated_at, brief, warnings, ads[advertiser,industry,likes,ctr,format,caption,link,thumbnail] / briefings[date,ad_count,headline])가 Task 2 생산 = Task 5 소비와 일치. `thumbnail` 로컬 경로(`thumbs/<date>/<NN>.jpg`)를 app.js가 `data/` 접두사로 참조 — 일치.
