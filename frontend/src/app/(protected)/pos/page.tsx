"use client";

import { AxiosError } from "axios";
import { useState } from "react";

import { apiClient } from "@/lib/api-client";
import { addOrIncrementCartLine } from "@/lib/cart";
import { getErrorMessage } from "@/lib/errors";
import { calculateSubtotal, calculateTax, calculateTotal } from "@/lib/pos-calculations";
import { BarcodeScanner } from "@/components/BarcodeScanner";
import { Button, Card, ErrorBanner, Field, Select, SuccessBanner, TextInput } from "@/components/ui";
import { ApiErrorDetail, CheckoutRequest, CheckoutResponse, Member, PaymentMethod, SkuLookup } from "@/types/api";

// 表示専用の概算税率。スタッフ向けAPIには現行税率を取得する手段がないため、
// カート画面のプレビュー計算にのみ用いる（会計時の確定額は必ずサーバー側で
// 再計算され、不一致であれば422で警告・再確認フローに入る。設計仕様書3.4節）。
const PREVIEW_TAX_RATE = 10;

interface CartLine {
  sku_id: string;
  product_name: string;
  size_code: string;
  color_code: string;
  quantity: number;
  reference_price: number;
  store_stock: number;
}

const PAYMENT_METHODS: { value: PaymentMethod; label: string }[] = [
  { value: "CASH", label: "現金" },
  { value: "CREDIT_CARD", label: "クレジットカード" },
  { value: "QR_CODE", label: "QRコード決済" },
  { value: "IC", label: "ICカード" },
];

export default function PosPage() {
  const [barcode, setBarcode] = useState("");
  const [scanError, setScanError] = useState<string | null>(null);
  const [cameraOpen, setCameraOpen] = useState(false);
  const [cart, setCart] = useState<CartLine[]>([]);

  const [memberId, setMemberId] = useState("");
  const [confirmedMember, setConfirmedMember] = useState<Member | null>(null);
  const [memberError, setMemberError] = useState<string | null>(null);

  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>("CASH");
  const [amountTendered, setAmountTendered] = useState("");

  const [checkoutError, setCheckoutError] = useState<string | null>(null);
  const [pendingMismatchTotal, setPendingMismatchTotal] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [receipt, setReceipt] = useState<CheckoutResponse | null>(null);

  const previewSubtotal = calculateSubtotal(
    cart.map((line) => ({ unitPrice: line.reference_price, quantity: line.quantity }))
  );
  const previewTax = calculateTax(previewSubtotal, PREVIEW_TAX_RATE);
  const previewTotal = calculateTotal(previewSubtotal, 0, previewTax);

  async function addSkuByBarcode(code: string) {
    setScanError(null);
    try {
      const response = await apiClient.get<SkuLookup>(`/skus/barcode/${encodeURIComponent(code)}`);
      const sku = response.data;
      if (!sku.is_active) {
        setScanError("この商品は現在販売停止中です。");
        return;
      }
      setCart((prev) => {
        const { cart: next, rejected } = addOrIncrementCartLine(prev, {
          sku_id: sku.sku_id,
          product_name: sku.product_name,
          size_code: sku.size_code,
          color_code: sku.color_code,
          quantity: 1,
          reference_price: sku.reference_price,
          store_stock: sku.store_stock,
        });
        if (rejected) {
          setScanError("購入リストの上限（100SKU）に達しています。");
        }
        return next;
      });
    } catch (err) {
      setScanError(getErrorMessage(err, "商品が見つかりませんでした。"));
    }
  }

  async function handleScan(event: React.FormEvent) {
    event.preventDefault();
    const code = barcode.trim();
    if (!code) return;
    await addSkuByBarcode(code);
    setBarcode("");
  }

  function handleCameraDetected(code: string) {
    setCameraOpen(false);
    void addSkuByBarcode(code);
  }

  function updateQuantity(skuId: string, quantity: number) {
    const clamped = Math.max(1, Math.min(99, Math.floor(quantity) || 1));
    setCart((prev) =>
      prev.map((line) => (line.sku_id === skuId ? { ...line, quantity: clamped } : line))
    );
  }

  function removeLine(skuId: string) {
    setCart((prev) => prev.filter((line) => line.sku_id !== skuId));
  }

  async function handleMemberLookup() {
    setMemberError(null);
    setConfirmedMember(null);
    const id = memberId.trim();
    if (!id) return;
    try {
      const response = await apiClient.get<Member>(`/members/${encodeURIComponent(id)}`);
      setConfirmedMember(response.data);
    } catch (err) {
      setMemberError(getErrorMessage(err, "会員が見つかりませんでした。"));
    }
  }

  function clearMember() {
    setMemberId("");
    setConfirmedMember(null);
    setMemberError(null);
  }

  function resetAfterSuccess() {
    setCart([]);
    setPendingMismatchTotal(null);
    clearMember();
    setAmountTendered("");
    setPaymentMethod("CASH");
  }

  async function submitCheckout(clientTotal: number) {
    setSubmitting(true);
    setCheckoutError(null);
    try {
      const payload: CheckoutRequest = {
        items: cart.map((line) => ({ sku_id: line.sku_id, quantity: line.quantity })),
        client_total: clientTotal,
        payment_method: paymentMethod,
        member_id: confirmedMember?.member_id,
        amount_tendered:
          paymentMethod === "CASH" && amountTendered ? Number(amountTendered) : undefined,
      };
      const response = await apiClient.post<CheckoutResponse>("/pos/checkout", payload);
      setReceipt(response.data);
      resetAfterSuccess();
    } catch (err) {
      if (err instanceof AxiosError && err.response?.status === 422) {
        const detail = err.response.data?.detail as ApiErrorDetail | undefined;
        if (detail?.error === "PRICE_MISMATCH" && typeof detail.current_total === "number") {
          setPendingMismatchTotal(detail.current_total);
          setSubmitting(false);
          return;
        }
        if (
          detail?.error === "INSUFFICIENT_PAYMENT" &&
          typeof detail.required === "number" &&
          typeof detail.tendered === "number"
        ) {
          setCheckoutError(
            `お預かり金額が不足しています（合計 ¥${detail.required.toLocaleString()} に対し ¥${detail.tendered.toLocaleString()} をお預かりしました）。`
          );
          setPendingMismatchTotal(null);
          setSubmitting(false);
          return;
        }
      }
      setCheckoutError(getErrorMessage(err, "会計処理に失敗しました。"));
      setPendingMismatchTotal(null);
    } finally {
      setSubmitting(false);
    }
  }

  function handleCheckoutClick() {
    setReceipt(null);
    setPendingMismatchTotal(null);
    void submitCheckout(previewTotal);
  }

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
      <div className="lg:col-span-2">
        <Card className="mb-6">
          <h2 className="mb-3 text-lg font-semibold">バーコード / SKU スキャン</h2>
          <form onSubmit={handleScan} className="flex gap-2">
            <TextInput
              value={barcode}
              onChange={(e) => setBarcode(e.target.value)}
              placeholder="EAN-13バーコードを入力してEnter"
              autoFocus
            />
            <Button type="submit">追加</Button>
            <Button type="button" variant="secondary" onClick={() => setCameraOpen(true)}>
              📷 カメラで読取
            </Button>
          </form>
          {scanError && <p className="mt-2 text-sm text-red-600">{scanError}</p>}
          {cameraOpen && (
            <BarcodeScanner
              onDetected={handleCameraDetected}
              onClose={() => setCameraOpen(false)}
            />
          )}
        </Card>

        <Card>
          <h2 className="mb-3 text-lg font-semibold">購入リスト</h2>
          {cart.length === 0 ? (
            <p className="text-sm text-gray-500">商品がまだ追加されていません。</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-gray-500">
                  <th className="py-2">商品</th>
                  <th className="py-2">サイズ/カラー</th>
                  <th className="py-2">単価(参考)</th>
                  <th className="py-2">数量</th>
                  <th className="py-2">小計(参考)</th>
                  <th className="py-2"></th>
                </tr>
              </thead>
              <tbody>
                {cart.map((line) => (
                  <tr key={line.sku_id} className="border-b last:border-0">
                    <td className="py-2">{line.product_name}</td>
                    <td className="py-2">
                      {line.size_code} / {line.color_code}
                    </td>
                    <td className="py-2">¥{line.reference_price.toLocaleString()}</td>
                    <td className="py-2">
                      <input
                        type="number"
                        min={1}
                        max={99}
                        value={line.quantity}
                        onChange={(e) => updateQuantity(line.sku_id, Number(e.target.value))}
                        className="w-16 rounded border border-gray-300 px-2 py-1"
                      />
                    </td>
                    <td className="py-2">
                      ¥{(line.reference_price * line.quantity).toLocaleString()}
                    </td>
                    <td className="py-2">
                      <button
                        onClick={() => removeLine(line.sku_id)}
                        className="text-xs text-red-600 hover:underline"
                      >
                        削除
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      </div>

      <div>
        <Card className="mb-6">
          <h2 className="mb-3 text-lg font-semibold">会員（任意）</h2>
          {confirmedMember ? (
            <div className="flex items-center justify-between text-sm">
              <span>
                {confirmedMember.member_name}（残ポイント {confirmedMember.point_balance}）
              </span>
              <button onClick={clearMember} className="text-xs text-red-600 hover:underline">
                解除
              </button>
            </div>
          ) : (
            <div className="flex gap-2">
              <TextInput
                value={memberId}
                onChange={(e) => setMemberId(e.target.value)}
                placeholder="会員ID"
              />
              <Button type="button" variant="secondary" onClick={handleMemberLookup}>
                照会
              </Button>
            </div>
          )}
          {memberError && <p className="mt-2 text-sm text-red-600">{memberError}</p>}
        </Card>

        <Card>
          <h2 className="mb-3 text-lg font-semibold">会計</h2>

          <Field label="支払方法" htmlFor="payment-method">
            <Select
              id="payment-method"
              value={paymentMethod}
              onChange={(e) => setPaymentMethod(e.target.value as PaymentMethod)}
            >
              {PAYMENT_METHODS.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </Select>
          </Field>

          {paymentMethod === "CASH" && (
            <Field label="お預かり金額" htmlFor="amount-tendered">
              <TextInput
                id="amount-tendered"
                type="number"
                min={0}
                value={amountTendered}
                onChange={(e) => setAmountTendered(e.target.value)}
              />
            </Field>
          )}

          <dl className="mb-4 space-y-1 text-sm">
            <div className="flex justify-between">
              <dt className="text-gray-500">小計(参考・税抜)</dt>
              <dd>¥{previewSubtotal.toLocaleString()}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">消費税(参考・概算10%)</dt>
              <dd>¥{previewTax.toLocaleString()}</dd>
            </div>
            <div className="flex justify-between text-base font-semibold">
              <dt>合計(参考)</dt>
              <dd>¥{previewTotal.toLocaleString()}</dd>
            </div>
          </dl>

          {checkoutError && <ErrorBanner message={checkoutError} />}

          {pendingMismatchTotal !== null && (
            <div className="mb-4 rounded border border-yellow-300 bg-yellow-50 p-3 text-sm text-yellow-800">
              <p className="mb-2">
                値引き・税率の適用によりサーバー確定額が ¥{pendingMismatchTotal.toLocaleString()}{" "}
                に更新されました。この金額で確定しますか？
              </p>
              <Button
                type="button"
                onClick={() => void submitCheckout(pendingMismatchTotal)}
                disabled={submitting}
              >
                この金額で確定する
              </Button>
            </div>
          )}

          <Button
            type="button"
            className="w-full"
            disabled={cart.length === 0 || submitting}
            onClick={handleCheckoutClick}
          >
            {submitting ? "処理中..." : "会計確定"}
          </Button>
        </Card>

        {receipt && (
          <Card className="mt-6">
            <SuccessBanner message="会計が完了しました。" />
            <dl className="space-y-1 text-sm">
              <div className="flex justify-between">
                <dt className="text-gray-500">取引ID</dt>
                <dd className="font-mono text-xs">{receipt.transaction_id}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">小計(税抜)</dt>
                <dd>¥{receipt.subtotal_ex_tax.toLocaleString()}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">値引き</dt>
                <dd>-¥{receipt.discount_total.toLocaleString()}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">消費税</dt>
                <dd>¥{receipt.tax_amount.toLocaleString()}</dd>
              </div>
              <div className="flex justify-between text-base font-semibold">
                <dt>合計(税込)</dt>
                <dd>¥{receipt.total_inc_tax.toLocaleString()}</dd>
              </div>
              {receipt.change > 0 && (
                <div className="flex justify-between">
                  <dt className="text-gray-500">お釣り</dt>
                  <dd>¥{receipt.change.toLocaleString()}</dd>
                </div>
              )}
            </dl>
          </Card>
        )}
      </div>
    </div>
  );
}
