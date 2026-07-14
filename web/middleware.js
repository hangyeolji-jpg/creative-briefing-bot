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
