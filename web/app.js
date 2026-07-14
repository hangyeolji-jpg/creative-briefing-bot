const listEl = document.getElementById("brief-list");
const detailEl = document.getElementById("detail");

async function loadJSON(path) {
  const res = await fetch(path, { cache: "no-store" });
  if (!res.ok) throw new Error(`${path} → ${res.status}`);
  return res.json();
}

function fmtPct(v) { return v == null ? "–" : `${Math.round(v * 100)}%`; }
function fmtNum(v) { return v == null ? "–" : v.toLocaleString(); }
// 따옴표까지 escape — 결과값이 href="..." 같은 속성 컨텍스트에 들어가므로
// " 를 남겨두면 속성을 탈출해 이벤트 핸들러를 주입할 수 있다.
function esc(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

// 아주 간단한 마크다운 → HTML (제목/굵게/문단만). 입력은 먼저 이스케이프.
// 제목은 줄 단위로 판정한다 — 블록 첫 줄만 보면 빈 줄 없이 이어진 제목이
// <p> 안에 중첩돼 잘못된 HTML이 된다.
function miniMarkdown(md) {
  const lines = esc(md)
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .split("\n");
  const out = [];
  let para = [];
  const flush = () => {
    if (para.length) { out.push(`<p>${para.join("<br>")}</p>`); para = []; }
  };
  for (const line of lines) {
    const heading = line.match(/^#{1,6}\s?(.*)$/);
    if (heading) { flush(); out.push(`<h3>${heading[1]}</h3>`); }
    else if (!line.trim()) flush();
    else para.push(line);
  }
  flush();
  return out.join("");
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
