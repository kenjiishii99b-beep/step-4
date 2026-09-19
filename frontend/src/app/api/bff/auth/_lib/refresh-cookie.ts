import { NextResponse } from "next/server";

const REFRESH_TOKEN_COOKIE = "refresh_token";
const REFRESH_TOKEN_PATH = "/api/bff/auth";
const REFRESH_TOKEN_MAX_AGE_SECONDS = 8 * 60 * 60; // 8時間（設計仕様書 3.1節）

/**
 * BFF (Next.js) が Refresh Token を HttpOnly Cookie として終端するための設定。
 * ブラウザには Refresh Token そのものを一切返さない。
 */
function refreshCookieOptions(maxAge: number) {
  return {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "strict" as const,
    path: REFRESH_TOKEN_PATH,
    maxAge,
  };
}

/**
 * Cookie の削除は Set-Cookie の Path が発行時と完全一致しない限りブラウザに
 * 無視される（RFC 6265）。発行時と同じ Path を明示して削除する。
 */
function clearRefreshCookie(response: NextResponse): void {
  response.cookies.delete({ name: REFRESH_TOKEN_COOKIE, path: REFRESH_TOKEN_PATH });
}

export {
  REFRESH_TOKEN_COOKIE,
  REFRESH_TOKEN_MAX_AGE_SECONDS,
  clearRefreshCookie,
  refreshCookieOptions,
};
