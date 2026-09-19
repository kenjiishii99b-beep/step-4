import { test, expect } from "@playwright/test";

import {
  E2E_MANAGER,
  INVENTORY_TEST_STORE_STOCK,
  INVENTORY_TEST_WAREHOUSE_STOCK,
  login,
  resetE2eFixtures,
  SKU_3_ID,
} from "./fixtures";

// UT-09: 在庫移動 / 店長による在庫移動（正常）
// MANAGERで在庫移動 → 移動元減、移動先増、履歴保存（画面表示で確認）。
test("店長が店舗から倉庫へ在庫を移動すると両拠点の在庫が正しく増減する", async ({ page }) => {
  // 移動前の絶対値を検証するため、実行順・実行回数に依存しないよう毎回リセットする。
  resetE2eFixtures();
  await login(page, E2E_MANAGER);
  await page.goto("/inventory");

  // 移動前の状態を照会画面で確認する（seed直後の固定値）。
  await page.getByPlaceholder("SKU ID").fill(SKU_3_ID);
  await page.getByRole("button", { name: "照会" }).click();
  const storeStockDd = page.locator("dt", { hasText: "店舗在庫" }).locator("xpath=following-sibling::dd[1]");
  const warehouseStockDd = page
    .locator("dt", { hasText: "倉庫在庫" })
    .locator("xpath=following-sibling::dd[1]");
  await expect(storeStockDd).toHaveText(String(INVENTORY_TEST_STORE_STOCK));
  await expect(warehouseStockDd).toHaveText(String(INVENTORY_TEST_WAREHOUSE_STOCK));

  const transferQuantity = 10;

  // 「SKU ID」「数量」ラベルは入荷登録フォームと重複するため、id指定で一意にする。
  await page.locator("#transfer-sku").fill(SKU_3_ID);
  await page.locator("#transfer-from").selectOption("STORE");
  await page.locator("#transfer-to").selectOption("WAREHOUSE");
  await page.locator("#transfer-qty").fill(String(transferQuantity));
  await page.getByRole("button", { name: "在庫移動" }).click();

  const expectedStore = INVENTORY_TEST_STORE_STOCK - transferQuantity;
  const expectedWarehouse = INVENTORY_TEST_WAREHOUSE_STOCK + transferQuantity;
  await expect(
    page.getByText(
      `在庫を移動しました（店舗在庫: ${expectedStore} / 倉庫在庫: ${expectedWarehouse}）`
    )
  ).toBeVisible();

  // 在庫照会側の表示も更新されている（同一SKUのため再照会と同じレスポンスが反映される）。
  await expect(storeStockDd).toHaveText(String(expectedStore));
  await expect(warehouseStockDd).toHaveText(String(expectedWarehouse));
});
