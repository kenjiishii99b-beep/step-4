import { NextRequest, NextResponse } from "next/server";

import { StaffSession } from "@/types/auth";

import { backendAuthUrl } from "../_lib/backend-url";
import { REFRESH_TOKEN_COOKIE, clearRefreshCookie } from "../_lib/refresh-cookie";

const REAUTH_REQUIRED = "認証が必要です。再度ログインしてください。";

/**
 * HttpOnly Cookie 内の Refresh Token から Access Token を再発行する。
 * ブラウザは Refresh Token を一切扱わない（Cookie は自動送信されるのみ）。
 */
export async function POST(req: NextRequest): Promise<NextResponse> {
  const refreshToken = req.cookies.get(REFRESH_TOKEN_COOKIE)?.value;
  if (!refreshToken) {
    return NextResponse.json({ detail: REAUTH_REQUIRED }, { status: 401 });
  }

  const backendResponse = await fetch(backendAuthUrl("refresh"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });

  if (!backendResponse.ok) {
    const status = backendResponse.status === 401 ? 401 : backendResponse.status;
    const response = NextResponse.json({ detail: REAUTH_REQUIRED }, { status });
    if (status === 401) {
      clearRefreshCookie(response);
    }
    return response;
  }

  const session = (await backendResponse.json()) as StaffSession;
  return NextResponse.json<StaffSession>(session);
}
