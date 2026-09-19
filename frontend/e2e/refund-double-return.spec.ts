import { test, expect } from "@playwright/test";

import { getStoreStock, login, SKU_1_BARCODE } from "./fixtures";

// UT-06: 返品 / 二重返品（異常）
// 同じ商品を再返品しようとするとエラーになり、在庫が二重に復元されないことを検証する。
test("同一SKUを二重に返品しようとするとエラーになり在庫が二重復元されない", async ({ page }) => {
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

  // 1回目の返品（正常）。
  await page.goto("/pos/refund-exchange");
  await page.getByPlaceholder("取引ID（例: TX-20260911-XXXXXXXX）").fill(transactionId);
  await page.getByRole("button", { name: "照会" }).click();
  await page.locator("table input[type='number']").first().fill("1");
  await page.getByRole("button", { name: "金額を計算する" }).click();
  await expect(page.getByText(/サーバー確定額は/)).toBeVisible();
  await page.getByRole("button", { name: "この金額で確定する" }).click();
  await expect(page.getByText("返品が完了しました。")).toBeVisible();

  const stockAfterFirstReturn = getStoreStock("E2E-PRODUCT-1-M-BLK");

  // 同一元取引を再度照会し、同じSKUをもう一度返品しようとする（二重返品）。
  await page.goto("/pos/refund-exchange");
  await page.getByPlaceholder("取引ID（例: TX-20260911-XXXXXXXX）").fill(transactionId);
  await page.getByRole("button", { name: "照会" }).click();
  await page.locator("table input[type='number']").first().fill("1");
  await page.getByRole("button", { name: "金額を計算する" }).click();

  // 元取引の購入数量(1)を超える返品要求として、サーバー側で拒否される。
  await expect(page.getByText("RETURN_QUANTITY_EXCEEDED")).toBeVisible();
  await expect(page.getByText("返品が完了しました。")).not.toBeVisible();

  // 在庫は1回目の返品分から変化しない（二重復元されない）。
  expect(getStoreStock("E2E-PRODUCT-1-M-BLK")).toBe(stockAfterFirstReturn);
});
