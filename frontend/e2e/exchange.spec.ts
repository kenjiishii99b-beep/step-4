import { test, expect } from "@playwright/test";

import { getStoreStock, login, SKU_1_BARCODE, SKU_2_BARCODE } from "./fixtures";

// UT-07: 交換 / 商品交換（正常）
// 元商品を指定→交換商品を指定 → 元商品在庫+1、交換商品在庫-1 となることを検証する。
test("元商品を返品し交換商品を指定すると在庫が正しく増減する", async ({ page }) => {
  await login(page);

  // 元取引を作成する（SKU_1を1点購入）。
  const barcodeInput = page.getByPlaceholder("EAN-13バーコードを入力してEnter");
  await barcodeInput.fill(SKU_1_BARCODE);
  await barcodeInput.press("Enter");
  await page.getByLabel("お預かり金額").fill("2750");
  await page.getByRole("button", { name: "会計確定" }).click();
  await expect(page.getByText("会計が完了しました。")).toBeVisible();

  const transactionId = await page
    .locator("dt", { hasText: "取引ID" })
    .locator("xpath=following-sibling::dd[1]")
    .innerText();

  const skuOneStockBefore = getStoreStock("E2E-PRODUCT-1-M-BLK");
  const skuTwoStockBefore = getStoreStock("E2E-PRODUCT-2-M-BLK");

  await page.goto("/pos/refund-exchange");
  await page.getByPlaceholder("取引ID（例: TX-20260911-XXXXXXXX）").fill(transactionId);
  await page.getByRole("button", { name: "照会" }).click();

  // 返品対象（元商品）を1点指定する。
  const qtyInput = page.locator("table input[type='number']").first();
  await qtyInput.fill("1");

  // 交換モードに切り替え、交換先商品(SKU_2)をスキャンする。
  await page.getByLabel("交換（別商品と差額精算）にする").check();
  await page.getByPlaceholder("交換先商品のバーコード").fill(SKU_2_BARCODE);
  await page.getByRole("button", { name: "追加" }).click();
  await expect(page.getByText("E2E Pants")).toBeVisible();

  await page.getByRole("button", { name: "金額を計算する" }).click();
  await expect(page.getByText(/サーバー確定額は/)).toBeVisible();
  await page.getByRole("button", { name: "この金額で確定する" }).click();

  await expect(page.getByText("交換が完了しました。")).toBeVisible();

  expect(getStoreStock("E2E-PRODUCT-1-M-BLK")).toBe(skuOneStockBefore + 1);
  expect(getStoreStock("E2E-PRODUCT-2-M-BLK")).toBe(skuTwoStockBefore - 1);
});
