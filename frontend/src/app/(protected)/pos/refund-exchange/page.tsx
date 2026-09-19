"use client";

import { AxiosError } from "axios";
import { useState } from "react";

import { Button, Card, ErrorBanner, Field, Select, SuccessBanner, TextInput } from "@/components/ui";
import { apiClient } from "@/lib/api-client";
import { getErrorMessage } from "@/lib/errors";
import {
  ApiErrorDetail,
  CheckoutItem,
  PaymentMethod,
  RefundExchangeRequest,
  RefundExchangeResponse,
  SkuLookup,
} from "@/types/api";

interface TransactionItem {
  sku_id: string;
  product_id: string;
  quantity: number;
  unit_price_snapshot: number;
  line_total_inc_tax: number;
}

interface TransactionDetail {
  transaction_id: string;
  tx_type: string;
  total_inc_tax: number;
  created_at: string;
  items: TransactionItem[];
}

interface ExchangeLine {
  sku_id: string;
  product_name: string;
  size_code: string;
  color_code: string;
  quantity: number;
}

const PAYMENT_METHODS: { value: PaymentMethod; label: string }[] = [
  { value: "CASH", label: "現金" },
  { value: "CREDIT_CARD", label: "クレジットカード" },
  { value: "QR_CODE", label: "QRコード決済" },
  { value: "IC", label: "ICカード" },
];

export default function RefundExchangePage() {
  const [parentTransactionId, setParentTransactionId] = useState("");
  const [transaction, setTransaction] = useState<TransactionDetail | null>(null);
  const [lookupError, setLookupError] = useState<string | null>(null);

  const [returnQuantities, setReturnQuantities] = useState<Record<string, number>>({});

  const [exchangeMode, setExchangeMode] = useState(false);
  const [exchangeBarcode, setExchangeBarcode] = useState("");
  const [exchangeLines, setExchangeLines] = useState<ExchangeLine[]>([]);
  const [exchangeScanError, setExchangeScanError] = useState<string | null>(null);

  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>("CASH");
  const [amountTendered, setAmountTendered] = useState("");

  const [pendingTotal, setPendingTotal] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [result, setResult] = useState<RefundExchangeResponse | null>(null);

  async function handleLookup(event: React.FormEvent) {
    event.preventDefault();
    setLookupError(null);
    setTransaction(null);
    setResult(null);
    const id = parentTransactionId.trim();
    if (!id) return;

    try {
      const response = await apiClient.get<TransactionDetail>(`/transactions/${encodeURIComponent(id)}`);
      if (response.data.tx_type !== "SALE") {
        setLookupError("この取引は返品・交換の対象にできません（通常販売のみ対象）。");
        return;
      }
      setTransaction(response.data);
      setReturnQuantities({});
    } catch (err) {
      setLookupError(getErrorMessage(err, "取引が見つかりませんでした。"));
    }
  }

  function setReturnQty(skuId: string, qty: number, max: number) {
    const clamped = Math.max(0, Math.min(max, Math.floor(qty) || 0));
    setReturnQuantities((prev) => ({ ...prev, [skuId]: clamped }));
  }

  async function handleExchangeScan(event: React.FormEvent) {
    event.preventDefault();
    setExchangeScanError(null);
    const code = exchangeBarcode.trim();
    if (!code) return;
    try {
      const response = await apiClient.get<SkuLookup>(`/skus/barcode/${encodeURIComponent(code)}`);
      const sku = response.data;
      if (!sku.is_active) {
        setExchangeScanError("この商品は現在販売停止中です。");
        return;
      }
      setExchangeLines((prev) => {
        const existing = prev.find((l) => l.sku_id === sku.sku_id);
        if (existing) {
          return prev.map((l) =>
            l.sku_id === sku.sku_id ? { ...l, quantity: Math.min(99, l.quantity + 1) } : l
          );
        }
        return [
          ...prev,
          {
            sku_id: sku.sku_id,
            product_name: sku.product_name,
            size_code: sku.size_code,
            color_code: sku.color_code,
            quantity: 1,
          },
        ];
      });
      setExchangeBarcode("");
    } catch (err) {
      setExchangeScanError(getErrorMessage(err, "商品が見つかりませんでした。"));
    }
  }

  function removeExchangeLine(skuId: string) {
    setExchangeLines((prev) => prev.filter((l) => l.sku_id !== skuId));
  }

  function buildReturnItems(): CheckoutItem[] {
    if (!transaction) return [];
    return transaction.items
      .filter((item) => (returnQuantities[item.sku_id] ?? 0) > 0)
      .map((item) => ({ sku_id: item.sku_id, quantity: returnQuantities[item.sku_id] }));
  }

  function resetForm() {
    setParentTransactionId("");
    setTransaction(null);
    setReturnQuantities({});
    setExchangeMode(false);
    setExchangeLines([]);
    setAmountTendered("");
    setPaymentMethod("CASH");
    setPendingTotal(null);
  }

  async function submit(clientTotal: number) {
    if (!transaction) return;
    const returnItems = buildReturnItems();
    if (returnItems.length === 0) {
      setFormError("返品する商品を1点以上指定してください。");
      return;
    }
    if (exchangeMode && exchangeLines.length === 0) {
      setFormError("交換モードでは交換商品を1点以上スキャンしてください。");
      return;
    }

    setSubmitting(true);
    setFormError(null);
    try {
      const payload: RefundExchangeRequest = {
        parent_transaction_id: transaction.transaction_id,
        tx_type: exchangeMode ? "EXCHANGE" : "RETURN",
        return_items: returnItems,
        exchange_items: exchangeMode
          ? exchangeLines.map((l) => ({ sku_id: l.sku_id, quantity: l.quantity }))
          : [],
        client_total: clientTotal,
        payment_method: paymentMethod,
        amount_tendered:
          paymentMethod === "CASH" && amountTendered ? Number(amountTendered) : undefined,
      };
      const response = await apiClient.post<RefundExchangeResponse>("/pos/refund-exchange", payload);
      setResult(response.data);
      resetForm();
    } catch (err) {
      if (err instanceof AxiosError && err.response?.status === 422) {
        const detail = err.response.data?.detail as ApiErrorDetail | undefined;
        if (detail?.error === "PRICE_MISMATCH" && typeof detail.current_total === "number") {
          setPendingTotal(detail.current_total);
          setSubmitting(false);
          return;
        }
        if (
          detail?.error === "INSUFFICIENT_PAYMENT" &&
          typeof detail.required === "number" &&
          typeof detail.tendered === "number"
        ) {
          setFormError(
            `お預かり金額が不足しています（請求額 ¥${detail.required.toLocaleString()} に対し ¥${detail.tendered.toLocaleString()} をお預かりしました）。`
          );
          setPendingTotal(null);
          setSubmitting(false);
          return;
        }
      }
      setFormError(getErrorMessage(err, "返品・交換処理に失敗しました。"));
      setPendingTotal(null);
    } finally {
      setSubmitting(false);
    }
  }

  function handleCalculate() {
    setResult(null);
    setPendingTotal(null);
    // 返品分は元取引時点の単価スナップショットで按分計算されるため、
    // フロントエンドでは事前に金額を算出できない。サーバーへ問い合わせて
    // 確定額を取得し、ユーザーに再確認させる（設計仕様書3.4節の想定フロー）。
    void submit(0);
  }

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
      <div className="lg:col-span-2 space-y-6">
        <Card>
          <h2 className="mb-3 text-lg font-semibold">元取引の照会</h2>
          <form onSubmit={handleLookup} className="flex gap-2">
            <TextInput
              value={parentTransactionId}
              onChange={(e) => setParentTransactionId(e.target.value)}
              placeholder="取引ID（例: TX-20260911-XXXXXXXX）"
            />
            <Button type="submit">照会</Button>
          </form>
          {lookupError && <p className="mt-2 text-sm text-red-600">{lookupError}</p>}
        </Card>

        {transaction && (
          <Card>
            <h2 className="mb-3 text-lg font-semibold">返品対象を選択</h2>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-gray-500">
                  <th className="py-2">SKU</th>
                  <th className="py-2">購入数量</th>
                  <th className="py-2">単価</th>
                  <th className="py-2">返品数量</th>
                </tr>
              </thead>
              <tbody>
                {transaction.items.map((item) => (
                  <tr key={item.sku_id} className="border-b last:border-0">
                    <td className="py-2 font-mono text-xs">{item.sku_id}</td>
                    <td className="py-2">{item.quantity}</td>
                    <td className="py-2">¥{item.unit_price_snapshot.toLocaleString()}</td>
                    <td className="py-2">
                      <input
                        type="number"
                        min={0}
                        max={item.quantity}
                        value={returnQuantities[item.sku_id] ?? 0}
                        onChange={(e) =>
                          setReturnQty(item.sku_id, Number(e.target.value), item.quantity)
                        }
                        className="w-16 rounded border border-gray-300 px-2 py-1"
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            <label className="mt-4 flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={exchangeMode}
                onChange={(e) => setExchangeMode(e.target.checked)}
              />
              交換（別商品と差額精算）にする
            </label>

            {exchangeMode && (
              <div className="mt-3 border-t pt-3">
                <form onSubmit={handleExchangeScan} className="mb-3 flex gap-2">
                  <TextInput
                    value={exchangeBarcode}
                    onChange={(e) => setExchangeBarcode(e.target.value)}
                    placeholder="交換先商品のバーコード"
                  />
                  <Button type="submit" variant="secondary">
                    追加
                  </Button>
                </form>
                {exchangeScanError && (
                  <p className="mb-2 text-sm text-red-600">{exchangeScanError}</p>
                )}
                {exchangeLines.length > 0 && (
                  <ul className="space-y-1 text-sm">
                    {exchangeLines.map((line) => (
                      <li key={line.sku_id} className="flex items-center justify-between">
                        <span>
                          {line.product_name}（{line.size_code}/{line.color_code}） ×{" "}
                          {line.quantity}
                        </span>
                        <button
                          onClick={() => removeExchangeLine(line.sku_id)}
                          className="text-xs text-red-600 hover:underline"
                        >
                          削除
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </Card>
        )}
      </div>

      <div>
        <Card>
          <h2 className="mb-3 text-lg font-semibold">精算</h2>
          <Field label="精算方法" htmlFor="refund-payment-method">
            <Select
              id="refund-payment-method"
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
            <Field label="お預かり金額（差額請求時）" htmlFor="refund-amount-tendered">
              <TextInput
                id="refund-amount-tendered"
                type="number"
                min={0}
                value={amountTendered}
                onChange={(e) => setAmountTendered(e.target.value)}
              />
            </Field>
          )}

          {formError && <ErrorBanner message={formError} />}

          {pendingTotal !== null && (
            <div className="mb-4 rounded border border-yellow-300 bg-yellow-50 p-3 text-sm text-yellow-800">
              <p className="mb-2">
                サーバー確定額は ¥{pendingTotal.toLocaleString()} です
                （マイナスは返金、プラスは追加請求）。この金額で確定しますか？
              </p>
              <Button type="button" onClick={() => void submit(pendingTotal)} disabled={submitting}>
                この金額で確定する
              </Button>
            </div>
          )}

          <Button
            type="button"
            className="w-full"
            disabled={!transaction || submitting}
            onClick={handleCalculate}
          >
            {submitting ? "処理中..." : "金額を計算する"}
          </Button>
        </Card>

        {result && (
          <Card className="mt-6">
            <SuccessBanner
              message={result.tx_type === "EXCHANGE" ? "交換が完了しました。" : "返品が完了しました。"}
            />
            <dl className="space-y-1 text-sm">
              <div className="flex justify-between">
                <dt className="text-gray-500">取引ID</dt>
                <dd className="font-mono text-xs">{result.transaction_id}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">元取引ID</dt>
                <dd className="font-mono text-xs">{result.parent_transaction_id}</dd>
              </div>
              <div className="flex justify-between text-base font-semibold">
                <dt>差額合計</dt>
                <dd>¥{result.total_inc_tax.toLocaleString()}</dd>
              </div>
              {result.change > 0 && (
                <div className="flex justify-between">
                  <dt className="text-gray-500">お釣り</dt>
                  <dd>¥{result.change.toLocaleString()}</dd>
                </div>
              )}
            </dl>
          </Card>
        )}
      </div>
    </div>
  );
}
