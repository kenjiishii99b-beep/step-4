import { addOrIncrementCartLine } from "@/lib/cart";

interface TestLine {
  sku_id: string;
  quantity: number;
}

function makeCart(size: number): TestLine[] {
  return Array.from({ length: size }, (_, i) => ({ sku_id: `SKU-${i}`, quantity: 1 }));
}

describe("addOrIncrementCartLine", () => {
  test("既存SKUを追加すると数量が加算される", () => {
    const cart: TestLine[] = [{ sku_id: "SKU-1", quantity: 2 }];
    const result = addOrIncrementCartLine(cart, { sku_id: "SKU-1", quantity: 3 });
    expect(result.rejected).toBe(false);
    expect(result.cart).toEqual([{ sku_id: "SKU-1", quantity: 5 }]);
  });

  test("既存SKUの数量加算は99でクランプされる", () => {
    const cart: TestLine[] = [{ sku_id: "SKU-1", quantity: 97 }];
    const result = addOrIncrementCartLine(cart, { sku_id: "SKU-1", quantity: 10 });
    expect(result.rejected).toBe(false);
    expect(result.cart[0].quantity).toBe(99);
  });

  test("新規SKUはリストに追加される", () => {
    const cart: TestLine[] = [{ sku_id: "SKU-1", quantity: 1 }];
    const result = addOrIncrementCartLine(cart, { sku_id: "SKU-2", quantity: 1 });
    expect(result.rejected).toBe(false);
    expect(result.cart).toHaveLength(2);
  });

  // FE-U10: 購入リストSKU上限（境界）— 100SKUまで登録
  test("99SKU登録済みの状態で新規SKUを追加すると100SKUになる", () => {
    const cart = makeCart(99);
    const result = addOrIncrementCartLine(cart, { sku_id: "SKU-NEW", quantity: 1 });
    expect(result.rejected).toBe(false);
    expect(result.cart).toHaveLength(100);
  });

  // FE-U10: 101SKU目は追加不可
  test("100SKU登録済みの状態で新規SKU（101SKU目）を追加すると拒否される", () => {
    const cart = makeCart(100);
    const result = addOrIncrementCartLine(cart, { sku_id: "SKU-NEW", quantity: 1 });
    expect(result.rejected).toBe(true);
    expect(result.cart).toHaveLength(100);
    expect(result.cart).toBe(cart);
  });

  test("100SKU登録済みでも既存SKUの数量加算は拒否されない", () => {
    const cart = makeCart(100);
    const result = addOrIncrementCartLine(cart, { sku_id: "SKU-0", quantity: 1 });
    expect(result.rejected).toBe(false);
    expect(result.cart).toHaveLength(100);
    expect(result.cart[0].quantity).toBe(2);
  });
});
