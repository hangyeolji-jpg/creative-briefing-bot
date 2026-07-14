// Vercel Edge Middleware — 모든 요청에 HTTP Basic Auth 강제.
// 환경변수 SITE_PASSWORD 와 일치하는 비밀번호만 통과.
export const config = { matcher: "/((?!favicon.ico).*)" };

export default function middleware(request) {
  const expected = process.env.SITE_PASSWORD || "";

  // 비번 미설정이면 열어주는 게 아니라 잠근다(fail-closed). 환경변수 오타 하나로
  // 비공개 아카이브가 아무 신호 없이 공개되는 쪽이 훨씬 위험하다.
  // (로컬은 python -m http.server 로 띄우므로 이 미들웨어 자체가 실행되지 않는다.)
  if (!expected) {
    return new Response(
      "SITE_PASSWORD 환경변수가 설정되지 않아 사이트가 잠겨 있습니다. Vercel 프로젝트 설정에서 추가하세요.",
      { status: 503, headers: { "Content-Type": "text/plain; charset=utf-8" } },
    );
  }

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
    headers: {
      "WWW-Authenticate": 'Basic realm="briefing-archive"',
      "Content-Type": "text/plain; charset=utf-8",
    },
  });
}
