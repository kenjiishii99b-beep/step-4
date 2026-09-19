import { MAX_CART_SKUS, MAX_QUANTITY } from "@/lib/validation";

interface CartLineLike {
  sku_id: string;
  quantity: number;
}

export interface AddToCartResult<T> {
  cart: T[];
  /** 購入リストが上限（100SKU）に達しており追加できなかった場合に true。 */
  rejected: boolean;
}

/**
 * 購入リストへSKUを追加する。既存SKUなら数量を加算（99でクランプ）、
 * 新規SKUなら追加するが、リストが既に100SKUに達している場合は追加しない
 * （設計仕様書8節チェックリスト：購入リスト最大100SKU）。
 */
export function addOrIncrementCartLine<T extends CartLineLike>(
  cart: T[],
  newLine: T
): AddToCartResult<T> {
  const existingIndex = cart.findIndex((line) => line.sku_id === newLine.sku_id);
  if (existingIndex >= 0) {
    const updated = [...cart];
    const current = updated[existingIndex];
    updated[existingIndex] = {
      ...current,
      quantity: Math.min(MAX_QUANTITY, current.quantity + newLine.quantity),
    };
    return { cart: updated, rejected: false };
  }

  if (cart.length >= MAX_CART_SKUS) {
    return { cart, rejected: true };
  }

  return { cart: [...cart, newLine], rejected: false };
}
