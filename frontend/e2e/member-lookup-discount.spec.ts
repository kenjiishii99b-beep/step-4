import { test, expect } from "@playwright/test";

import {
  E2E_MEMBER_DISCOUNT_RATE,
  E2E_MEMBER_ID,
  E2E_MEMBER_NAME,
  E2E_MEMBER_POINT_BALANCE,
  login,
  SKU_1_BARCODE,
} from "./fixtures";

// UT-14: 会員 / 会員コード照会（正常）
// 会員IDの照会で会員情報が正しく反映され、会員向け値引きが会計に正しく適用されることを検証する。
test("会員IDを照会すると会員情報が表示され、会計に会員値引きが反映される", async ({ page }) => {
  await login(page);

  await page.getByPlaceholder("会員ID").fill(E2E_MEMBER_ID);
  await page.getByRole("button", { name: "照会" }).click();
  await expect(
    page.getByText(`${E2E_MEMBER_NAME}（残ポイント ${E2E_MEMBER_POINT_BALANCE}）`)
  ).toBeVisible();

  const barcodeInput = page.getByPlaceholder("EAN-13バーコードを入力してEnter");
  await barcodeInput.fill(SKU_1_BARCODE);
  await barcodeInput.press("Enter");
  await page.getByLabel("お預かり金額").fill("3000");

  // クライアント側プレビューは値引き非考慮（合計¥2,750）で送信するため、
  // サーバー確定額（会員値引き適用後）との不一致による再確認フローを経て確定する。
  await page.getByRole("button", { name: "会計確定" }).click();

  const subtotal = 2500;
  const discount = Math.floor((subtotal * E2E_MEMBER_DISCOUNT_RATE) / 100); // 250
  const taxable = subtotal - discount; // 2250
  const tax = Math.floor((taxable * 10) / 100); // 225
  const total = taxable + tax; // 2475

  await expect(
    page.getByText(`値引き・税率の適用によりサーバー確定額が ¥${total.toLocaleString()} に更新されました。この金額で確定しますか？`)
  ).toBeVisible();
  await page.getByRole("button", { name: "この金額で確定する" }).click();

  await expect(page.getByText("会計が完了しました。")).toBeVisible();
  await expect(page.getByText(`-¥${discount.toLocaleString()}`)).toBeVisible(); // 値引き行
  await expect(page.getByText(`¥${total.toLocaleString()}`)).toBeVisible(); // 合計(税込)
  await expect(page.getByText(`¥${(3000 - total).toLocaleString()}`)).toBeVisible(); // お釣り
});
