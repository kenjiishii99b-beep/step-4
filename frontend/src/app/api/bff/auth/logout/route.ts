import { NextResponse } from "next/server";

import { clearRefreshCookie } from "../_lib/refresh-cookie";

/**
 * ログアウト。設計仕様書のエンドポイント表にバックエンド側のログアウトAPIは
 * 定義されていない（JWTはサーバー側で失効管理しない設計のため）。
 * ここでは BFF が保持する Refresh Token の HttpOnly Cookie を破棄するのみ。
 * ブラウザ側の Access Token（メモリ上）は呼び出し元が破棄する。
 */
export async function POST(): Promise<NextResponse> {
  const response = NextResponse.json({ ok: true });
  clearRefreshCookie(response);
  return response;
}
