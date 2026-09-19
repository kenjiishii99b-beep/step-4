import { StaffSession } from "@/types/auth";

/**
 * Access Token をメモリ上でのみ保持する（設計仕様書 3.1節：localStorage等の
 * 永続ストレージへの保存禁止）。axios インターセプターと React の
 * AuthContext の両方から参照できるよう、モジュールスコープの単純な
 * pub/sub ストアとして実装する。
 */
let currentSession: StaffSession | null = null;
type Listener = (session: StaffSession | null) => void;
const listeners = new Set<Listener>();

function getSession(): StaffSession | null {
  return currentSession;
}

function setSession(next: StaffSession | null): void {
  currentSession = next;
  listeners.forEach((listener) => listener(next));
}

function subscribeSession(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

let refreshPromise: Promise<StaffSession | null> | null = null;

/**
 * HttpOnly Cookie 内の Refresh Token から Access Token を再発行する。
 * axios のインターセプターからも呼ばれるため、循環参照を避けて素の fetch を使う。
 * 同時に複数箇所から呼ばれても実際のリクエストは1回にまとめる。
 */
async function refreshSession(): Promise<StaffSession | null> {
  if (!refreshPromise) {
    refreshPromise = fetch("/api/bff/auth/refresh", {
      method: "POST",
      credentials: "include",
    })
      .then(async (response) => {
        if (!response.ok) {
          setSession(null);
          return null;
        }
        const data = (await response.json()) as StaffSession;
        setSession(data);
        return data;
      })
      .catch(() => {
        setSession(null);
        return null;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

export { getSession, refreshSession, setSession, subscribeSession };
