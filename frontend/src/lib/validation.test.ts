import { isQuantityValid, isValidEan13Format } from "@/lib/validation";

describe("isQuantityValid", () => {
  // FE-U04: 数量下限・上限（境界・正常）
  test.each([1, 99])("数量%i（下限・上限）はバリデーション通過する", (quantity) => {
    expect(isQuantityValid(quantity)).toBe(true);
  });

  // FE-U05: 数量範囲外（境界・異常）
  test.each([0, 100])("数量%iは範囲外のためバリデーションエラーになる", (quantity) => {
    expect(isQuantityValid(quantity)).toBe(false);
  });

  test("負の数量はバリデーションエラーになる", () => {
    expect(isQuantityValid(-1)).toBe(false);
  });

  test("整数でない数量はバリデーションエラーになる", () => {
    expect(isQuantityValid(1.5)).toBe(false);
  });
});

describe("isValidEan13Format", () => {
  // FE-U06: EAN-13形式（正常）
  test("半角数字13桁は受付可能", () => {
    expect(isValidEan13Format("4901234567894")).toBe(true);
  });

  // FE-U07: EAN-13桁数不正（異常）
  test.each([
    ["490123456789", "12桁"],
    ["49012345678945", "14桁"],
  ])("%s（%s）は入力エラーになる", (code) => {
    expect(isValidEan13Format(code)).toBe(false);
  });

  // FE-U08: 英字・記号混入（異常）
  test.each([
    ["490123456789A", "英字混入"],
    ["4901234-67894", "記号混入"],
  ])("%s（%s）は入力エラーになる", (code) => {
    expect(isValidEan13Format(code)).toBe(false);
  });

  test("空文字は入力エラーになる", () => {
    expect(isValidEan13Format("")).toBe(false);
  });
});
