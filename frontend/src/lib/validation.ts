/** 購入リスト1行あたりの数量の下限・上限（設計仕様書8節チェックリスト）。 */
export const MIN_QUANTITY = 1;
export const MAX_QUANTITY = 99;

/** 購入リストに登録できるSKU数の上限。 */
export const MAX_CART_SKUS = 100;

/** 数量が1〜99の整数範囲内かを検証する。 */
export function isQuantityValid(quantity: number): boolean {
  return Number.isInteger(quantity) && quantity >= MIN_QUANTITY && quantity <= MAX_QUANTITY;
}

/** EAN-13形式（半角数字13桁）かどうかを検証する。 */
export function isValidEan13Format(code: string): boolean {
  return /^[0-9]{13}$/.test(code);
}
