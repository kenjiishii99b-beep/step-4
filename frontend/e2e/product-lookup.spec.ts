import { test, expect } from "@playwright/test";

import { login, SKU_2_BARCODE } from "./fixtures";

// UT-13: 商品 / 商品検索・詳細表示（正常）
// EAN-13バーコードでの商品照会（レジのバーコードスキャンが商品検索の実体）で、
// 正しい商品情報（商品名・サイズ/カラー・単価・小計）が表示されることを検証する。
test("EAN-13バーコードで商品照会すると正しい商品情報が表示される", async ({ page }) => {
  await login(page);

  const barcodeInput = page.getByPlaceholder("EAN-13バーコードを入力してEnter");
  await barcodeInput.fill(SKU_2_BARCODE);
  await barcodeInput.press("Enter");

  const row = page.locator("table tbody tr").first();
  await expect(row).toContainText("E2E Pants");
  await expect(row).toContainText("M / BLK");
  await expect(row).toContainText("¥4,800"); // 単価(参考)
  await expect(row.locator("input[type='number']")).toHaveValue("1");
  await expect(row).toContainText("¥4,800"); // 小計(参考) = 単価×数量1
});
