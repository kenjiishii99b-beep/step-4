import { test, expect } from "@playwright/test";

import { login, SKU_1_BARCODE } from "./fixtures";

// UT-12: 認証 / セッション更新
// Access Tokenの期限切れをAPIレスポンスの401で擬似的に再現し、
// (1) Refresh Tokenが有効な場合は自動再認証により操作が継続すること、
// (2) Refresh Tokenも無効な場合は再ログイン画面へ遷移することを検証する。

test("アクセストークン期限切れでも自動リフレッシュにより操作が継続する（正常）", async ({ page }) => {
  await login(page);

  let barcodeCallCount = 0;
  await page.route("**/api/bff/skus/barcode/**", async (route) => {
    barcodeCallCount++;
    if (barcodeCallCount === 1) {
      await route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "認証が必要です。再度ログインしてください。" }),
      });
      return;
    }
    await route.continue();
  });

  const barcodeInput = page.getByPlaceholder("EAN-13バーコードを入力してEnter");
  await barcodeInput.fill(SKU_1_BARCODE);
  await barcodeInput.press("Enter");

  // 1回目は擬似的な401だが、有効なRefresh Tokenで自動再認証され、
  // リトライされた2回目のリクエストでカート追加が成功する。
  await expect(page.locator("table").getByText("E2E Tee")).toBeVisible();
  expect(barcodeCallCount).toBeGreaterThanOrEqual(2);
});

test("リフレッシュトークンも無効な場合は再ログイン画面へ遷移する（異常）", async ({ page }) => {
  await login(page);

  await page.route("**/api/bff/skus/barcode/**", (route) =>
    route.fulfill({
      status: 401,
      contentType: "application/json",
      body: JSON.stringify({ detail: "認証が必要です。再度ログインしてください。" }),
    })
  );
  await page.route("**/api/bff/auth/refresh", (route) =>
    route.fulfill({
      status: 401,
      contentType: "application/json",
      body: JSON.stringify({ detail: "再認証が必要です。" }),
    })
  );

  const barcodeInput = page.getByPlaceholder("EAN-13バーコードを入力してEnter");
  await barcodeInput.fill(SKU_1_BARCODE);
  await barcodeInput.press("Enter");

  // アクセス・リフレッシュとも無効なため再認証に失敗し、ログイン画面へ戻される。
  await expect(page).toHaveURL(/\/login$/);
});
