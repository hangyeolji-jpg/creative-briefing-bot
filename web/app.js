const listEl = document.getElementById("brief-list");
const detailEl = document.getElementById("detail");

async function loadJSON(path) {
  const res = await fetch(path, { cache: "no-store" });
  if (!res.ok) throw new Error(`${path} → ${res.status}`);
  return res.json();
}

function fmtPct(v) { return v == null ? "–" : `${Math.round(v * 100)}%`; }
function fmtNum(v) { return v == null ? "–" : v.toLocaleString(); }
function fmtDuration(sec) { return sec == null ? "–" : `${Math.round(sec)}초`; }

// 따옴표까지 escape — 결과값이 href="..." 같은 속성 컨텍스트에 들어가므로
// " 를 남겨두면 속성을 탈출해 이벤트 핸들러를 주입할 수 있다.
function esc(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

/* ---------------- 마크다운 ----------------
   브리핑은 제목·불릿(2단)·굵게·기울임으로 온다. 불릿을 리스트로 렌더링하지
   않으면 전부 <br>로 이어붙은 한 덩어리 글이 되어 읽을 수가 없다. */

function mdInline(s) {
  // **굵게**를 먼저 소비해야 남은 *기울임*이 안전하게 잡힌다.
  return esc(s)
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>");
}

function listHtml(items) {
  let html = '<ul class="md-list">';
  for (let i = 0; i < items.length; i++) {
    if (items[i].depth > 0) continue; // 자식은 부모가 함께 그린다
    const kids = [];
    let j = i + 1;
    while (j < items.length && items[j].depth > 0) { kids.push(items[j]); j++; }
    html += `<li>${mdInline(items[i].text)}`;
    if (kids.length) {
      html += '<ul class="md-sub">' +
        kids.map((k) => `<li>${mdInline(k.text)}</li>`).join("") + "</ul>";
    }
    html += "</li>";
    i = j - 1;
  }
  return html + "</ul>";
}

// 제목을 뺀 본문 줄들 → HTML (문단 / 불릿 리스트 / 구분선)
function renderBody(lines) {
  const out = [];
  let para = [];
  let items = [];

  const flushPara = () => {
    if (!para.length) return;
    out.push(`<p>${para.map(mdInline).join("<br>")}</p>`);
    para = [];
  };
  const flushList = () => {
    if (!items.length) return;
    out.push(listHtml(items));
    items = [];
  };

  for (const raw of lines) {
    const bullet = raw.match(/^(\s*)[*\-+]\s+(.*)$/);
    if (bullet) {
      flushPara();
      items.push({ depth: bullet[1].length >= 2 ? 1 : 0, text: bullet[2] });
      continue;
    }
    if (/^\s*-{3,}\s*$/.test(raw)) { flushPara(); flushList(); continue; }
    if (!raw.trim()) { flushPara(); flushList(); continue; }
    flushList();
    para.push(raw.trim());
  }
  flushPara();
  flushList();
  return out.join("");
}

// 브리핑을 "### 1. 제목" 기준으로 쪼갠다. 프롬프트가 4개 섹션을 고정하므로
// 그 구조를 화면에서도 살린다.
function splitSections(md) {
  const sections = [];
  let cur = { num: null, title: null, lines: [] };
  for (const raw of String(md || "").split("\n")) {
    const h = raw.match(/^#{1,6}\s+(?:(\d+)[.)]\s*)?(.*)$/);
    if (h) {
      sections.push(cur);
      cur = { num: h[1] || null, title: h[2].trim(), lines: [] };
    } else {
      cur.lines.push(raw);
    }
  }
  sections.push(cur);
  return sections.filter((s) => s.title || s.lines.join("").trim());
}

function renderBrief(md) {
  const sections = splitSections(md);
  return sections
    .map((s) => {
      const body = renderBody(s.lines);
      if (!s.title) {
        // 제목 앞의 도입부 / 말미 각주
        return body ? `<div class="brief-intro">${body}</div>` : "";
      }
      const num = s.num
        ? `<span class="sec-num">${esc(s.num)}</span>`
        : "";
      return `
        <section class="brief-section">
          <h3 class="sec-title">${num}${esc(s.title)}</h3>
          <div class="sec-body">${body}</div>
        </section>`;
    })
    .join("");
}

/* ---------------- 요약 지표 ---------------- */

function median(nums) {
  if (!nums.length) return null;
  const s = [...nums].sort((a, b) => a - b);
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

function summaryTiles(ads) {
  if (!ads.length) return "";
  const ctrs = ads.map((a) => a.ctr).filter((v) => v != null);
  const durs = ads.map((a) => a.duration).filter((v) => v != null);

  const objCount = {};
  ads.forEach((a) => { if (a.objective) objCount[a.objective] = (objCount[a.objective] || 0) + 1; });
  const topObj = Object.entries(objCount).sort((a, b) => b[1] - a[1])[0];

  const tiles = [
    {
      label: "수집 광고",
      value: `${ads.length}건`,
      sub: "TikTok 인기순",
    },
    ctrs.length && {
      label: "클릭률",
      value: `${fmtPct(Math.min(...ctrs))} – ${fmtPct(Math.max(...ctrs))}`,
      sub: `중앙값 ${fmtPct(median(ctrs))}`,
    },
    durs.length && {
      label: "영상 길이",
      value: `${fmtDuration(Math.min(...durs))} – ${fmtDuration(Math.max(...durs))}`,
      sub: `중앙값 ${fmtDuration(median(durs))}`,
    },
    topObj && {
      label: "주요 캠페인 목표",
      value: esc(topObj[0]),
      sub: `${topObj[1]}건 / 전체 ${ads.length}건`,
    },
  ].filter(Boolean);

  return `<dl class="summary">${tiles
    .map((t) => `
      <div class="tile">
        <dt>${t.label}</dt>
        <dd>${t.value}<span class="tile-sub">${t.sub}</span></dd>
      </div>`)
    .join("")}</dl>`;
}

/* ---------------- 광고 카드 ---------------- */

// 0~1 범위의 클릭률을 막대 너비(%)로. 값이 없으면 막대를 그리지 않는다.
function ctrMeter(ctr) {
  if (ctr == null) return "";
  const pct = Math.max(0, Math.min(100, Number(ctr) * 100));
  return `<div class="meter" role="img" aria-label="클릭률 ${fmtPct(ctr)}">
      <span style="width:${pct.toFixed(1)}%"></span>
    </div>`;
}

// index는 TikTok Top Ads의 인기 순위 — 카드 순서 자체가 정보라 번호로 드러낸다.
function adCard(ad, i) {
  const thumb = ad.thumbnail
    ? `<img class="ad-thumb" src="data/${esc(ad.thumbnail)}" alt="" loading="lazy">`
    : `<div class="ad-thumb ad-thumb--empty">${ad.format === "video" ? "▶" : "🖼"}</div>`;

  const chips = [];
  if (ad.industry) chips.push(`<span class="chip">${esc(ad.industry)}</span>`);
  if (ad.objective) chips.push(`<span class="chip chip--obj">${esc(ad.objective)}</span>`);

  const stats = [
    { label: "좋아요", value: fmtNum(ad.likes) },
    { label: "길이", value: fmtDuration(ad.duration) },
  ]
    .map((s) => `<div class="stat"><dt>${s.label}</dt><dd>${s.value}</dd></div>`)
    .join("");

  return `
    <a class="ad-card" href="${esc(ad.link)}" target="_blank" rel="noopener">
      <span class="ad-rank">${i + 1}</span>
      ${thumb}
      <div class="ad-body">
        <span class="ad-advertiser">${esc(ad.advertiser) || "광고주 미공개"}</span>
        <div class="chips">${chips.join("")}</div>
        <p class="ad-caption">${esc(ad.caption)}</p>
        <div class="ad-metrics">
          <div class="ctr-row">
            <span class="ctr-label">클릭률</span>
            <span class="ctr-value">${fmtPct(ad.ctr)}</span>
          </div>
          ${ctrMeter(ad.ctr)}
          <dl class="stats">${stats}</dl>
        </div>
      </div>
    </a>`;
}

/* ---------------- 화면 ---------------- */

async function showBriefing(date) {
  detailEl.innerHTML = `<p class="muted">불러오는 중…</p>`;
  listEl.querySelectorAll("a").forEach((a) =>
    a.classList.toggle("active", a.dataset.date === date));
  try {
    const b = await loadJSON(`data/briefings/${date}.json`);
    const ads = b.ads || [];
    const warn = (b.warnings || []).length
      ? `<div class="warnings">${b.warnings.map((w) => `⚠️ ${esc(w)}`).join("<br>")}</div>`
      : "";
    const adsSection = ads.length
      ? `<div class="ads-head">
           <h3 class="ads-heading">인기 광고</h3>
           <span class="ads-note">인기순 ${ads.length}건 · 카드를 누르면 원본으로 이동합니다</span>
         </div>
         <div class="ad-grid">${ads.map(adCard).join("")}</div>`
      : `<div class="ads-head"><h3 class="ads-heading">인기 광고</h3></div>
         <p class="muted">이번 주에는 수집된 광고가 없습니다.</p>`;

    detailEl.innerHTML = `
      <div class="detail-head">
        <h2 class="detail-date">${esc(b.date)}</h2>
        <span class="detail-meta">주간 크리에이티브 인사이트</span>
      </div>
      ${warn}
      ${summaryTiles(ads)}
      <div class="brief">${renderBrief(b.brief)}</div>
      ${adsSection}`;
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

    // 링크의 기본 동작(해시 변경)을 그대로 두고 hashchange로 라우팅한다 —
    // preventDefault로 막으면 URL이 선택을 반영하지 않아 새로고침/공유가 깨진다.
    const known = new Set(briefings.map((b) => b.date));
    const fromHash = () => {
      const date = decodeURIComponent(location.hash.slice(1));
      return known.has(date) ? date : null;
    };
    window.addEventListener("hashchange", () => {
      const date = fromHash();
      if (date) showBriefing(date);
    });
    showBriefing(fromHash() || briefings[0].date);
  } catch (e) {
    detailEl.innerHTML = `<p class="muted">아카이브를 불러오지 못했습니다 (${esc(e.message)}).</p>`;
  }
}

init();
