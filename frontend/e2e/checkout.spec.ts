import { test, expect } from "@playwright/test";

import { login, SKU_1_BARCODE, SKU_2_BARCODE } from "./fixtures";

// UT-01: レジ販売 / 複数SKUスキャンと現金会計（正常）
// 2SKUをスキャン→現金決済→レシート表示までの一連の流れを実ブラウザ操作で検証する。
// （会員読取・割引適用は本テストでは扱わない。会員照会自体は別途 tests/test_members.py 等で検証済み。）
test("2SKUをスキャンして現金会計するとレシートが正しく表示される", async ({ page }) => {
  await login(page);

  const barcodeInput = page.getByPlaceholder("EAN-13バーコードを入力してEnter");
  await barcodeInput.fill(SKU_1_BARCODE);
  await barcodeInput.press("Enter");
  await expect(page.getByText("E2E Tee")).toBeVisible();

  await barcodeInput.fill(SKU_2_BARCODE);
  await barcodeInput.press("Enter");
  await expect(page.getByText("E2E Pants")).toBeVisible();

  // 税抜小計 2,500 + 4,800 = 7,300円、税額(10%floor) = 730円、税込合計 = 8,030円
  await expect(page.getByText("¥8,030")).toBeVisible();

  await page.getByLabel("お預かり金額").fill("10000");

  await page.getByRole("button", { name: "会計確定" }).click();

  await expect(page.getByText("会計が完了しました。")).toBeVisible();
  await expect(page.getByText("¥1,970")).toBeVisible(); // お釣り = 10,000 - 8,030

  // 会計完了後はカートがリセットされる。
  await expect(page.getByText("商品がまだ追加されていません。")).toBeVisible();
});
