import { calculateSubtotal, calculateTax, calculateTotal } from "@/lib/pos-calculations";

describe("calculateSubtotal", () => {
  // FE-U01: 単一SKUの小計計算（正常）
  test("単価1,000円・数量2の小計は2,000円", () => {
    expect(calculateSubtotal([{ unitPrice: 1000, quantity: 2 }])).toBe(2000);
  });

  test("複数行の小計は各行の単価×数量の合計", () => {
    const lines = [
      { unitPrice: 1000, quantity: 2 },
      { unitPrice: 500, quantity: 3 },
    ];
    expect(calculateSubtotal(lines)).toBe(3500);
  });

  test("空のカートの小計は0円", () => {
    expect(calculateSubtotal([])).toBe(0);
  });
});

describe("calculateTax", () => {
  // FE-U02: 外税端数処理（切捨て）（境界）
  test("税抜1,980円・税率10%の税額は198円（1円未満切捨て）", () => {
    expect(calculateTax(1980, 10)).toBe(198);
  });

  test("端数が出ない場合はそのまま計算される", () => {
    expect(calculateTax(2000, 10)).toBe(200);
  });

  test("税抜0円の税額は0円", () => {
    expect(calculateTax(0, 10)).toBe(0);
  });
});

describe("calculateTotal", () => {
  // FE-U02: 税込合計の計算
  test("税抜1,980円・税額198円の税込合計は2,178円", () => {
    expect(calculateTotal(1980, 0, 198)).toBe(2178);
  });

  // FE-U03: 値引きを含む合計計算（正常）
  test("値引きを差し引いた上で税額を加算した合計になる", () => {
    // 税抜小計3,000円から値引き500円を引いた2,500円に対する税額（250円）を加算
    const subtotal = 3000;
    const discount = 500;
    const tax = calculateTax(subtotal - discount, 10);
    expect(calculateTotal(subtotal, discount, tax)).toBe(subtotal - discount + tax);
    expect(calculateTotal(subtotal, discount, tax)).toBe(2750);
  });

  test("値引きが0円の場合は税抜小計+税額と一致する", () => {
    expect(calculateTotal(1000, 0, 100)).toBe(1100);
  });
});
