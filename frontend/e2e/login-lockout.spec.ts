import { test, expect } from "@playwright/test";

// UT-11: 認証 / ログイン失敗・ロック（異常）
// PW誤りを連続送信 → 5回失敗後にロック状態になることを実機ブラウザで検証する。
test("パスワード誤りを5回連続すると6回目でロックされる", async ({ page }) => {
  // IPバケットへの汚染を避けつつ再実行しても衝突しないよう、毎回ユニークなstaff_idを使う。
  const staffId = `E2E-LOCKOUT-${Date.now()}`;

  await page.goto("/login");

  for (let attempt = 1; attempt <= 5; attempt++) {
    await page.getByLabel("担当者ID").fill(staffId);
    await page.getByLabel("パスワード").fill("wrong-password");
    await page.getByRole("button", { name: "ログイン" }).click();
    await expect(page.getByText("IDまたはパスワードが正しくありません。")).toBeVisible();
  }

  // 6回目：staff_idバケットがロックされ、429由来のメッセージに切り替わる。
  await page.getByLabel("担当者ID").fill(staffId);
  await page.getByLabel("パスワード").fill("wrong-password");
  await page.getByRole("button", { name: "ログイン" }).click();
  await expect(
    page.getByText("ログイン試行回数が上限に達しました。しばらくしてから再度お試しください。")
  ).toBeVisible();

  // ロック中はページ遷移せずログイン画面に留まる。
  await expect(page).toHaveURL(/\/login$/);
});
