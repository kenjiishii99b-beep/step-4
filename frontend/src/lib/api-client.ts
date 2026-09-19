import axios, { AxiosError, InternalAxiosRequestConfig } from "axios";

import { getSession, refreshSession } from "./token-store";

/**
 * ブラウザから呼ぶのは常に同一オリジンの BFF（/api/bff/**）。
 * FastAPI の物理URLはサーバー側（src/app/api/bff/**）にしか存在せず、ここでは扱わない。
 */
export const apiClient = axios.create({
  baseURL: "/api/bff",
  withCredentials: true,
  headers: {
    "Content-Type": "application/json",
  },
});

apiClient.interceptors.request.use((config) => {
  const session = getSession();
  if (session?.access_token) {
    config.headers.Authorization = `Bearer ${session.access_token}`;
  }
  return config;
});

interface RetryableConfig extends InternalAxiosRequestConfig {
  _retry?: boolean;
}

// Access Token は15分で失効する（設計仕様書3.1節）。401を受けたら一度だけ
// Refresh Token（HttpOnly Cookie）でのサイレント再認証を試み、成功すれば
// 元のリクエストを再送する。
apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as RetryableConfig | undefined;
    if (error.response?.status === 401 && original && !original._retry) {
      original._retry = true;
      const session = await refreshSession();
      if (session) {
        original.headers.Authorization = `Bearer ${session.access_token}`;
        return apiClient(original);
      }
    }
    return Promise.reject(error);
  }
);
