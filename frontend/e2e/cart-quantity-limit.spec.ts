import { test, expect } from "@playwright/test";

import { login, SKU_1_BARCODE } from "./fixtures";

// UT-02: レジ販売 / SKU数量上限（境界）
// 同一SKUを99点まで登録できるが、100点目（+1）は不可であることを検証する。
test("同一SKUの数量は99が上限で、100点目は追加できない", async ({ page }) => {
  await login(page);

  const barcodeInput = page.getByPlaceholder("EAN-13バーコードを入力してEnter");
  await barcodeInput.fill(SKU_1_BARCODE);
  await barcodeInput.press("Enter");

  const quantityInput = page.locator('input[type="number"][min="1"][max="99"]');
  await expect(quantityInput).toHaveValue("1");

  // 直接99へ変更（UI側のクランプ: Math.min(99, ...)）
  await quantityInput.fill("99");
  await quantityInput.blur();
  await expect(quantityInput).toHaveValue("99");

  // 同一バーコードを再スキャン（addOrIncrementCartLineによる+1）しても99でクランプされる。
  await barcodeInput.fill(SKU_1_BARCODE);
  await barcodeInput.press("Enter");
  await expect(quantityInput).toHaveValue("99");

  // 100超を直接入力しても99にクランプされる（updateQuantity側のクランプ）。
  await quantityInput.fill("150");
  await quantityInput.blur();
  await expect(quantityInput).toHaveValue("99");
});
