import { execFileSync } from "node:child_process";
import path from "node:path";

import { Page, expect } from "@playwright/test";

const REPO_ROOT = path.resolve(__dirname, "..", "..");

/**
 * backend/scripts/seed_e2e_fixtures.py を再実行し、固定フィクスチャ
 * （在庫数含む）を既知の初期値へ戻す。在庫移動テストのように移動前後の
 * 絶対値を検証するテストでは、実行順・実行回数に依存しないようテスト前に呼ぶ。
 */
export function resetE2eFixtures(): void {
  execFileSync(
    "docker",
    ["compose", "exec", "-T", "backend", "python", "-m", "scripts.seed_e2e_fixtures"],
    { cwd: REPO_ROOT, encoding: "utf-8" }
  );
}

/**
 * このE2Eページには在庫数を表示する箇所がないSKUがあるため、
 * ローカルDocker環境のMySQLへ直接問い合わせて店舗在庫を検証する
 * （backend/tests のpytest統合テストがDBを直接検証するのと同様の手法）。
 */
export function getStoreStock(skuId: string): number {
  const output = execFileSync(
    "docker",
    [
      "compose",
      "exec",
      "-T",
      "mysql",
      "mysql",
      "-uroot",
      "-proot_password",
      "-N",
      "apparel_pos",
      "-e",
      `SELECT store_stock FROM skus WHERE sku_id='${skuId}';`,
    ],
    { cwd: REPO_ROOT, encoding: "utf-8" }
  );
  return Number(output.trim());
}

/**
 * backend/scripts/seed_e2e_fixtures.py で投入される固定E2Eフィクスチャ。
 * 在庫は毎回大きな値にリセットされるため、繰り返し実行しても枯渇しない。
 */
export const E2E_CASHIER = { staffId: "E2E-CASHIER", password: "E2ePlaywright!23" };
export const E2E_MANAGER = { staffId: "E2E-MANAGER", password: "E2ePlaywright!23" };

export const SKU_1_BARCODE = "4912345678901"; // E2E Tee
export const SKU_2_BARCODE = "4912345678932"; // E2E Pants

// 在庫移動テスト専用SKU。店舗在庫100・倉庫在庫0に毎回リセットされる。
export const SKU_3_ID = "E2E-PRODUCT-3-M-BLK";
export const INVENTORY_TEST_STORE_STOCK = 100;
export const INVENTORY_TEST_WAREHOUSE_STOCK = 0;

export const E2E_MEMBER_ID = "E2E-MEMBER-1";
export const E2E_MEMBER_NAME = "E2E Member";
export const E2E_MEMBER_POINT_BALANCE = 250;
// E2E_MEMBER会員に紐付く会員向け全体値引き（RATE 10%）。backend/scripts/seed_e2e_fixtures.py参照。
export const E2E_MEMBER_DISCOUNT_RATE = 10;

// UT-03（購入リストSKU上限）用。101種類の異なるSKUのバーコードを生成する。
export function bulkSkuBarcode(index: number): string {
  return `4999999${String(index).padStart(6, "0")}`;
}
export const BULK_SKU_COUNT = 101;

export async function login(
  page: Page,
  credentials: { staffId: string; password: string } = E2E_CASHIER
): Promise<void> {
  await page.goto("/login");
  await page.getByLabel("担当者ID").fill(credentials.staffId);
  await page.getByLabel("パスワード").fill(credentials.password);
  await page.getByRole("button", { name: "ログイン" }).click();
  await expect(page).toHaveURL(/\/pos$/);
}
