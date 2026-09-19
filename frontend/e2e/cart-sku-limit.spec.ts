import { test, expect } from "@playwright/test";

import { BULK_SKU_COUNT, bulkSkuBarcode, login } from "./fixtures";

// UT-03: レジ販売 / 購入リスト上限（境界）
// 異なるSKUを100種類まで登録できるが、101種類目は追加できないことを検証する。
test("異なるSKUを100種類まで登録でき、101種類目は追加できない", async ({ page }) => {
  await login(page);

  const barcodeInput = page.getByPlaceholder("EAN-13バーコードを入力してEnter");
  const cartRows = page.locator("table tbody tr");

  for (let i = 1; i <= 100; i++) {
    await barcodeInput.fill(bulkSkuBarcode(i));
    await barcodeInput.press("Enter");
    // 次のスキャン入力とのステート競合を避けるため、直前のスキャン処理完了を待つ。
    await expect(barcodeInput).toHaveValue("");
  }

  await expect(cartRows).toHaveCount(100);

  // 101種類目（BULK_SKU_COUNT = 101）は上限超過のため追加されない。
  await barcodeInput.fill(bulkSkuBarcode(BULK_SKU_COUNT));
  await barcodeInput.press("Enter");
  await expect(page.getByText("購入リストの上限（100SKU）に達しています。")).toBeVisible();
  await expect(cartRows).toHaveCount(100);
});
