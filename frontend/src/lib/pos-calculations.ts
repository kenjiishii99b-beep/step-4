/**
 * POS画面のプレビュー計算（表示専用の概算値）。
 * 会計時の確定額は必ずサーバー側で再計算され、ここでの計算結果は
 * 参考表示にのみ用いる（設計仕様書3.4節：金額改ざん防止）。
 */

export interface SubtotalLine {
  unitPrice: number;
  quantity: number;
}

/** 税抜小計を計算する（各行の単価×数量の合計）。 */
export function calculateSubtotal(lines: SubtotalLine[]): number {
  return lines.reduce((sum, line) => sum + line.unitPrice * line.quantity, 0);
}

/** 外税方式の消費税額を計算する（1円未満切り捨て）。 */
export function calculateTax(subtotalExTax: number, taxRatePercent: number): number {
  return Math.floor((subtotalExTax * taxRatePercent) / 100);
}

/** 税抜小計・値引き合計・消費税額から税込合計を計算する。 */
export function calculateTotal(
  subtotalExTax: number,
  discountTotal: number,
  taxAmount: number
): number {
  return subtotalExTax - discountTotal + taxAmount;
}
