import { test, expect } from "@playwright/test";

import { login } from "./fixtures";

// UT-08: 在庫移動 / 一般スタッフの権限境界（異常）
// STAFFロールで在庫移動画面へアクセスすると、移動フォームが非表示になることを検証する。
test("STAFFロールでは店舗⇔倉庫の在庫移動フォームが表示されない", async ({ page }) => {
  await login(page); // デフォルトはE2E_CASHIER（STAFF）

  await page.goto("/inventory");

  await expect(page.getByText("店舗⇔倉庫の在庫移動は店長・システム管理者のみ実行できます。")).toBeVisible();
  await expect(page.getByText("店舗⇔倉庫 在庫移動")).not.toBeVisible();
  await expect(page.locator("#transfer-sku")).toHaveCount(0);
});
