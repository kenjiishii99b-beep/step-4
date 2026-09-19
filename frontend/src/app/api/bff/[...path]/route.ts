import { NextRequest, NextResponse } from "next/server";

/**
 * Next.js BFF: ブラウザ → ここ → FastAPI（内部通信）のリバースプロキシ。
 *
 * ブラウザは常に同一オリジンの /api/bff/** だけを呼び、FastAPI の物理URL
 * （BACKEND_INTERNAL_URL）はサーバー側のこのファイルにしか存在しない。
 *
 * 認証（Access/Refresh トークンの HttpOnly Cookie 変換など）はここに実装する。
 * 現時点では最小限の転送のみを行うプレースホルダー。
 */
const BACKEND_INTERNAL_URL = process.env.BACKEND_INTERNAL_URL ?? "http://localhost:8000";

async function proxy(req: NextRequest, path: string[]): Promise<NextResponse> {
  const targetUrl = new URL(`/api/v1/${path.join("/")}`, BACKEND_INTERNAL_URL);
  targetUrl.search = req.nextUrl.search;

  const headers = new Headers(req.headers);
  headers.delete("host");

  const response = await fetch(targetUrl, {
    method: req.method,
    headers,
    body: ["GET", "HEAD"].includes(req.method) ? undefined : await req.text(),
  });

  const responseHeaders = new Headers(response.headers);
  return new NextResponse(response.body, {
    status: response.status,
    headers: responseHeaders,
  });
}

export async function GET(req: NextRequest, { params }: { params: { path: string[] } }) {
  return proxy(req, params.path);
}

export async function POST(req: NextRequest, { params }: { params: { path: string[] } }) {
  return proxy(req, params.path);
}

export async function PUT(req: NextRequest, { params }: { params: { path: string[] } }) {
  return proxy(req, params.path);
}

export async function DELETE(req: NextRequest, { params }: { params: { path: string[] } }) {
  return proxy(req, params.path);
}
