import { NextRequest, NextResponse } from "next/server";

import { StaffSession } from "@/types/auth";

import { backendAuthUrl } from "../_lib/backend-url";
import {
  REFRESH_TOKEN_COOKIE,
  REFRESH_TOKEN_MAX_AGE_SECONDS,
  refreshCookieOptions,
} from "../_lib/refresh-cookie";

interface BackendLoginResponse extends StaffSession {
  refresh_token: string;
}

const GENERIC_INVALID_CREDENTIALS = "IDまたはパスワードが正しくありません。";

/**
 * ログイン。設計仕様書 2.3節①のシーケンス図のとおり、Refresh Token は
 * ここで HttpOnly/Secure/SameSite=Strict Cookie に変換し、ブラウザの
 * レスポンスボディには含めない。
 */
export async function POST(req: NextRequest): Promise<NextResponse> {
  const body = await req.text();

  const headers: Record<string, string> = { "Content-Type": "application/json" };
  // Next.js (App Router, Node ランタイム) は自前では生ソケットのリモート
  // アドレスを取得できないため、実クライアントIPは前段のリバースプロキシ
  // (Azure Front Door / App Gateway / Nginx 等) が設定する X-Forwarded-For
  // をそのまま中継する。前段プロキシが存在しないローカル開発環境では
  // このヘッダーは付かず、Backend 側は自身のIP単位制限にフォールバックする。
  const forwardedFor = req.headers.get("x-forwarded-for");
  if (forwardedFor) {
    headers["X-Forwarded-For"] = forwardedFor;
  }

  const backendResponse = await fetch(backendAuthUrl("login"), {
    method: "POST",
    headers,
    body,
  });

  if (backendResponse.status === 401) {
    return NextResponse.json({ detail: GENERIC_INVALID_CREDENTIALS }, { status: 401 });
  }

  if (!backendResponse.ok) {
    const errorBody = await backendResponse.text();
    return new NextResponse(errorBody, {
      status: backendResponse.status,
      headers: { "Content-Type": "application/json" },
    });
  }

  const data = (await backendResponse.json()) as BackendLoginResponse;
  const { refresh_token, ...session } = data;

  const response = NextResponse.json<StaffSession>(session);
  response.cookies.set(
    REFRESH_TOKEN_COOKIE,
    refresh_token,
    refreshCookieOptions(REFRESH_TOKEN_MAX_AGE_SECONDS)
  );
  return response;
}
