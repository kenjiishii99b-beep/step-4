"use client";

import { useState } from "react";

import { Button, Card, ErrorBanner, Field, Select, SuccessBanner, TextInput } from "@/components/ui";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { getErrorMessage } from "@/lib/errors";
import { InventoryReceiptRequest, InventoryStatus, InventoryTransferRequest, StockLocation } from "@/types/api";

export default function InventoryPage() {
  const { session } = useAuth();

  const [lookupSkuId, setLookupSkuId] = useState("");
  const [status, setStatus] = useState<InventoryStatus | null>(null);
  const [lookupError, setLookupError] = useState<string | null>(null);

  const [receiptSkuId, setReceiptSkuId] = useState("");
  const [receiptLocation, setReceiptLocation] = useState<StockLocation>("STORE");
  const [receiptQuantity, setReceiptQuantity] = useState("1");
  const [receiptMessage, setReceiptMessage] = useState<string | null>(null);
  const [receiptError, setReceiptError] = useState<string | null>(null);
  const [receiptSubmitting, setReceiptSubmitting] = useState(false);

  const [transferSkuId, setTransferSkuId] = useState("");
  const [fromLocation, setFromLocation] = useState<StockLocation>("WAREHOUSE");
  const [toLocation, setToLocation] = useState<StockLocation>("STORE");
  const [transferQuantity, setTransferQuantity] = useState("1");
  const [transferMessage, setTransferMessage] = useState<string | null>(null);
  const [transferError, setTransferError] = useState<string | null>(null);
  const [transferSubmitting, setTransferSubmitting] = useState(false);

  async function handleLookup(event: React.FormEvent) {
    event.preventDefault();
    setLookupError(null);
    setStatus(null);
    const id = lookupSkuId.trim();
    if (!id) return;
    try {
      const response = await apiClient.get<InventoryStatus>(`/inventory/${encodeURIComponent(id)}`);
      setStatus(response.data);
    } catch (err) {
      setLookupError(getErrorMessage(err, "SKUが見つかりませんでした。"));
    }
  }

  async function handleReceipt(event: React.FormEvent) {
    event.preventDefault();
    setReceiptError(null);
    setReceiptMessage(null);
    setReceiptSubmitting(true);
    try {
      const payload: InventoryReceiptRequest = {
        sku_id: receiptSkuId.trim(),
        location: receiptLocation,
        quantity: Number(receiptQuantity),
      };
      const response = await apiClient.post<InventoryStatus>("/inventory/receipt", payload);
      setReceiptMessage(
        `入荷を登録しました（店舗在庫: ${response.data.store_stock} / 倉庫在庫: ${response.data.warehouse_stock}）`
      );
      if (status && status.sku_id === response.data.sku_id) {
        setStatus(response.data);
      }
    } catch (err) {
      setReceiptError(getErrorMessage(err, "入荷登録に失敗しました。"));
    } finally {
      setReceiptSubmitting(false);
    }
  }

  async function handleTransfer(event: React.FormEvent) {
    event.preventDefault();
    setTransferError(null);
    setTransferMessage(null);
    if (fromLocation === toLocation) {
      setTransferError("移動元と移動先には異なる場所を指定してください。");
      return;
    }
    setTransferSubmitting(true);
    try {
      const payload: InventoryTransferRequest = {
        sku_id: transferSkuId.trim(),
        from_location: fromLocation,
        to_location: toLocation,
        quantity: Number(transferQuantity),
      };
      const response = await apiClient.post<InventoryStatus>("/inventory/transfer", payload);
      setTransferMessage(
        `在庫を移動しました（店舗在庫: ${response.data.store_stock} / 倉庫在庫: ${response.data.warehouse_stock}）`
      );
      if (status && status.sku_id === response.data.sku_id) {
        setStatus(response.data);
      }
    } catch (err) {
      setTransferError(getErrorMessage(err, "在庫移動に失敗しました。"));
    } finally {
      setTransferSubmitting(false);
    }
  }

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
      <Card>
        <h2 className="mb-3 text-lg font-semibold">在庫照会</h2>
        <form onSubmit={handleLookup} className="flex gap-2">
          <TextInput
            value={lookupSkuId}
            onChange={(e) => setLookupSkuId(e.target.value)}
            placeholder="SKU ID"
          />
          <Button type="submit">照会</Button>
        </form>
        {lookupError && <p className="mt-2 text-sm text-red-600">{lookupError}</p>}
        {status && (
          <dl className="mt-4 space-y-1 text-sm">
            <div className="flex justify-between">
              <dt className="text-gray-500">SKU</dt>
              <dd className="font-mono text-xs">{status.sku_id}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">店舗在庫</dt>
              <dd>{status.store_stock}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">倉庫在庫</dt>
              <dd>{status.warehouse_stock}</dd>
            </div>
          </dl>
        )}
      </Card>

      <Card>
        <h2 className="mb-3 text-lg font-semibold">入荷登録</h2>
        <form onSubmit={handleReceipt}>
          <Field label="SKU ID" htmlFor="receipt-sku">
            <TextInput
              id="receipt-sku"
              value={receiptSkuId}
              onChange={(e) => setReceiptSkuId(e.target.value)}
              required
            />
          </Field>
          <Field label="入荷先" htmlFor="receipt-location">
            <Select
              id="receipt-location"
              value={receiptLocation}
              onChange={(e) => setReceiptLocation(e.target.value as StockLocation)}
            >
              <option value="STORE">店舗</option>
              <option value="WAREHOUSE">倉庫</option>
            </Select>
          </Field>
          <Field label="数量" htmlFor="receipt-qty">
            <TextInput
              id="receipt-qty"
              type="number"
              min={1}
              value={receiptQuantity}
              onChange={(e) => setReceiptQuantity(e.target.value)}
              required
            />
          </Field>
          {receiptError && <ErrorBanner message={receiptError} />}
          {receiptMessage && <SuccessBanner message={receiptMessage} />}
          <Button type="submit" disabled={receiptSubmitting}>
            {receiptSubmitting ? "登録中..." : "入荷登録"}
          </Button>
        </form>
      </Card>

      {session && (session.role === "MANAGER" || session.role === "ADMIN") && (
        <Card>
          <h2 className="mb-3 text-lg font-semibold">店舗⇔倉庫 在庫移動</h2>
          <form onSubmit={handleTransfer}>
            <Field label="SKU ID" htmlFor="transfer-sku">
              <TextInput
                id="transfer-sku"
                value={transferSkuId}
                onChange={(e) => setTransferSkuId(e.target.value)}
                required
              />
            </Field>
            <div className="mb-3 grid grid-cols-2 gap-3">
              <Field label="移動元" htmlFor="transfer-from">
                <Select
                  id="transfer-from"
                  value={fromLocation}
                  onChange={(e) => setFromLocation(e.target.value as StockLocation)}
                >
                  <option value="STORE">店舗</option>
                  <option value="WAREHOUSE">倉庫</option>
                </Select>
              </Field>
              <Field label="移動先" htmlFor="transfer-to">
                <Select
                  id="transfer-to"
                  value={toLocation}
                  onChange={(e) => setToLocation(e.target.value as StockLocation)}
                >
                  <option value="STORE">店舗</option>
                  <option value="WAREHOUSE">倉庫</option>
                </Select>
              </Field>
            </div>
            <Field label="数量" htmlFor="transfer-qty">
              <TextInput
                id="transfer-qty"
                type="number"
                min={1}
                value={transferQuantity}
                onChange={(e) => setTransferQuantity(e.target.value)}
                required
              />
            </Field>
            {transferError && <ErrorBanner message={transferError} />}
            {transferMessage && <SuccessBanner message={transferMessage} />}
            <Button type="submit" disabled={transferSubmitting}>
              {transferSubmitting ? "移動中..." : "在庫移動"}
            </Button>
          </form>
        </Card>
      )}
      {session && session.role === "STAFF" && (
        <Card>
          <p className="text-sm text-gray-500">
            店舗⇔倉庫の在庫移動は店長・システム管理者のみ実行できます。
          </p>
        </Card>
      )}
    </div>
  );
}
