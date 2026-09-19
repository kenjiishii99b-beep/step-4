import { test, expect } from "@playwright/test";

import { login, SKU_1_BARCODE } from "./fixtures";

// UT-05: 返品 / 不正取引ID（異常）
// 存在しない取引ID、および返品・交換の対象外（通常販売以外）の取引IDを
// それぞれ照会した場合に、エラー表示のうえ処理が中断されることを検証する。
test("存在しない取引IDおよび対象外取引の照会はエラーとなり処理が中断する", async ({ page }) => {
  await login(page);

  // --- 存在しない取引ID ---
  await page.goto("/pos/refund-exchange");
  await page.getByPlaceholder("取引ID（例: TX-20260911-XXXXXXXX）").fill("TX-NONEXISTENT-00000000");
  await page.getByRole("button", { name: "照会" }).click();
  await expect(page.getByText("TRANSACTION_NOT_FOUND")).toBeVisible();
  await expect(page.getByText("返品対象を選択")).not.toBeVisible();

  // --- 対象外の取引（通常販売ではない取引） ---
  // まず元取引を作成し、正常に1点返品して RETURN 取引を作る。
  await page.goto("/pos");
  const barcodeInput = page.getByPlaceholder("EAN-13バーコードを入力してEnter");
  await barcodeInput.fill(SKU_1_BARCODE);
  await barcodeInput.press("Enter");
  await page.getByLabel("お預かり金額").fill("2750");
  await page.getByRole("button", { name: "会計確定" }).click();
  await expect(page.getByText("会計が完了しました。")).toBeVisible();
  const saleTransactionId = await page
    .locator("dt", { hasText: "取引ID" })
    .locator("xpath=following-sibling::dd[1]")
    .innerText();

  await page.goto("/pos/refund-exchange");
  await page.getByPlaceholder("取引ID（例: TX-20260911-XXXXXXXX）").fill(saleTransactionId);
  await page.getByRole("button", { name: "照会" }).click();
  await page.locator("table input[type='number']").first().fill("1");
  await page.getByRole("button", { name: "金額を計算する" }).click();
  await expect(page.getByText(/サーバー確定額は/)).toBeVisible();
  await page.getByRole("button", { name: "この金額で確定する" }).click();
  await expect(page.getByText("返品が完了しました。")).toBeVisible();
  // 結果カードには「取引ID」（今回のRETURN）と「元取引ID」の両方が表示されるため、完全一致で絞り込む。
  const returnTransactionId = await page
    .locator("dt", { hasText: /^取引ID$/ })
    .locator("xpath=following-sibling::dd[1]")
    .innerText();

  // 生成されたRETURN取引を、さらに返品・交換の「元取引」として照会すると対象外エラーになる。
  await page.getByPlaceholder("取引ID（例: TX-20260911-XXXXXXXX）").fill(returnTransactionId);
  await page.getByRole("button", { name: "照会" }).click();
  await expect(
    page.getByText("この取引は返品・交換の対象にできません（通常販売のみ対象）。")
  ).toBeVisible();
  await expect(page.getByText("返品対象を選択")).not.toBeVisible();
});
