import { test, expect } from "@playwright/test";

import { login, SKU_1_BARCODE } from "./fixtures";

// UT-04: 返品 / レシート照合返品（正常）
// 元取引ID照合→対象SKU選択→サーバー金額再計算→返品確定までの一連の流れを検証する。
test("元取引を照合してSKUを返品すると返品が完了する", async ({ page }) => {
  await login(page);

  // 元取引を作成する。
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
  expect(transactionId).toMatch(/^TX-/);

  await page.goto("/pos/refund-exchange");
  await page.getByPlaceholder("取引ID（例: TX-20260911-XXXXXXXX）").fill(transactionId);
  await page.getByRole("button", { name: "照会" }).click();

  // SKU行の返品数量入力（購入数量1点）に1を入力する。
  const qtyInput = page.locator("table input[type='number']").first();
  await qtyInput.fill("1");

  await page.getByRole("button", { name: "金額を計算する" }).click();

  // サーバー確定額の再確認ステップ（マイナス=返金）を経て確定する。
  await expect(page.getByText(/サーバー確定額は/)).toBeVisible();
  await page.getByRole("button", { name: "この金額で確定する" }).click();

  await expect(page.getByText("返品が完了しました。")).toBeVisible();
  await expect(page.getByText(transactionId).first()).toBeVisible();
});
