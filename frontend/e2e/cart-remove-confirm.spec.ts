import { test, expect } from "@playwright/test";

import { login, SKU_1_BARCODE } from "./fixtures";

// 要件3.3: 購入リストからの削除は確認ダイアログを経てから実行されることを検証する。
test("購入リストの削除はキャンセルすると残り、確認すると削除される", async ({ page }) => {
  await login(page);

  const barcodeInput = page.getByPlaceholder("EAN-13バーコードを入力してEnter");
  await barcodeInput.fill(SKU_1_BARCODE);
  await barcodeInput.press("Enter");
  const cartRows = page.locator("table tbody tr");
  await expect(cartRows).toHaveCount(1);

  // 1回目: キャンセルすると行は残る。
  page.once("dialog", (dialog) => dialog.dismiss());
  await page.getByRole("button", { name: "削除" }).click();
  await expect(cartRows).toHaveCount(1);

  // 2回目: 確認すると行が削除される。
  page.once("dialog", (dialog) => {
    expect(dialog.message()).toContain("E2E Tee");
    void dialog.accept();
  });
  await page.getByRole("button", { name: "削除" }).click();
  await expect(cartRows).toHaveCount(0);
});
