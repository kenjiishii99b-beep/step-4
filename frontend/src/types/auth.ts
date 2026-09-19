export type Role = "STAFF" | "MANAGER" | "ADMIN";

/**
 * ブラウザが受け取るログイン/リフレッシュ応答。
 * Access Token はここに含むが、Refresh Token は BFF が HttpOnly Cookie に
 * 変換するため含まれない。
 */
export interface StaffSession {
  access_token: string;
  token_type: string;
  staff_id: string;
  staff_name: string;
  role: Role;
}
