import { test, expect } from "@playwright/test";

import { login } from "./fixtures";

// 要件3.1: バーコード読取エラー時、商品ID+サイズ+カラーの手入力でSKUを追加できることを検証する。
test("バーコードが読み取れない場合、商品ID+サイズ+カラーの手入力でSKUを追加できる", async ({
  page,
}) => {
  await login(page);

  const barcodeInput = page.getByPlaceholder("EAN-13バーコードを入力してEnter");
  await barcodeInput.fill("0000000000000");
  await barcodeInput.press("Enter");
  await expect(page.getByText("SKU_NOT_FOUND")).toBeVisible();

  await page.getByText("読み取れない場合はSKUを直接指定する").click();
  await page.getByPlaceholder("商品ID").fill("E2E-PRODUCT-1");
  await page.getByPlaceholder("サイズ").fill("M");
  await page.getByPlaceholder("カラー").fill("BLK");
  await page.getByRole("button", { name: "検索して追加" }).click();

  await expect(page.locator("table").getByText("E2E Tee")).toBeVisible();
  await expect(page.getByText("「E2E Tee」を追加しました。")).toBeVisible();
});

test("手入力で存在しない組み合わせを検索するとエラーになる", async ({ page }) => {
  await login(page);

  const barcodeInput = page.getByPlaceholder("EAN-13バーコードを入力してEnter");
  await barcodeInput.fill("0000000000000");
  await barcodeInput.press("Enter");
  await page.getByText("読み取れない場合はSKUを直接指定する").click();
  await page.getByPlaceholder("商品ID").fill("NO-SUCH-PRODUCT");
  await page.getByPlaceholder("サイズ").fill("M");
  await page.getByPlaceholder("カラー").fill("BLK");
  await page.getByRole("button", { name: "検索して追加" }).click();

  await expect(page.getByText("SKU_NOT_FOUND")).toBeVisible();
});
