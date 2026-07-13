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
