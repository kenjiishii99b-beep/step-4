const BACKEND_INTERNAL_URL = process.env.BACKEND_INTERNAL_URL ?? "http://localhost:8000";

function backendAuthUrl(subPath: string): string {
  return new URL(`/api/v1/auth/${subPath}`, BACKEND_INTERNAL_URL).toString();
}

export { backendAuthUrl };
