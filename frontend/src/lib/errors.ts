import { AxiosError } from "axios";

interface ValidationErrorItem {
  msg?: string;
}

/**
 * バックエンドの HTTPException detail は文字列、
 * {error, message, ...} 形式のオブジェクト、または FastAPI 標準の
 * バリデーションエラー配列のいずれかで返ってくる。UI表示用に正規化する。
 */
export function getErrorMessage(error: unknown, fallback = "エラーが発生しました。"): string {
  if (error instanceof AxiosError) {
    const detail: unknown = error.response?.data?.detail;

    if (typeof detail === "string") {
      return detail;
    }

    if (Array.isArray(detail)) {
      const messages = (detail as ValidationErrorItem[])
        .map((item) => item.msg)
        .filter((msg): msg is string => Boolean(msg));
      if (messages.length > 0) {
        return messages.join(" / ");
      }
    }

    if (detail && typeof detail === "object") {
      const record = detail as Record<string, unknown>;
      if (typeof record.message === "string") {
        return record.message;
      }
      if (typeof record.error === "string") {
        return record.error;
      }
    }

    return error.message || fallback;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return fallback;
}
