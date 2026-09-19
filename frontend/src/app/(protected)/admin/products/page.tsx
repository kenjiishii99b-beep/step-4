"use client";

import { useState } from "react";

import { RoleGate } from "@/components/RoleGate";
import { Button, Card, ErrorBanner, Field, SuccessBanner, TextInput } from "@/components/ui";
import { apiClient } from "@/lib/api-client";
import { getErrorMessage } from "@/lib/errors";
import { ProductCreateRequest, ProductResponse, ProductUpdateRequest, SkuInput } from "@/types/api";

const emptySku: SkuInput = {
  sku_id: "",
  barcode_ean13: "",
  size_system_id: "STANDARD",
  size_code: "M",
  color_system_id: "BASIC",
  color_code: "BLK",
  store_stock: 0,
  warehouse_stock: 0,
};

function SkuRow({
  sku,
  onChange,
  onRemove,
}: {
  sku: SkuInput;
  onChange: (next: SkuInput) => void;
  onRemove: () => void;
}) {
  return (
    <div className="mb-2 grid grid-cols-8 gap-2 rounded border border-gray-200 p-2 text-sm">
      <input
        className="col-span-2 rounded border border-gray-300 px-2 py-1"
        placeholder="SKU ID"
        value={sku.sku_id}
        onChange={(e) => onChange({ ...sku, sku_id: e.target.value })}
      />
      <input
        className="col-span-2 rounded border border-gray-300 px-2 py-1"
        placeholder="バーコード(EAN-13)"
        value={sku.barcode_ean13}
        onChange={(e) => onChange({ ...sku, barcode_ean13: e.target.value })}
      />
      <input
        className="rounded border border-gray-300 px-2 py-1"
        placeholder="サイズ体系"
        value={sku.size_system_id}
        onChange={(e) => onChange({ ...sku, size_system_id: e.target.value })}
      />
      <input
        className="rounded border border-gray-300 px-2 py-1"
        placeholder="サイズ"
        value={sku.size_code}
        onChange={(e) => onChange({ ...sku, size_code: e.target.value })}
      />
      <input
        className="rounded border border-gray-300 px-2 py-1"
        placeholder="カラー体系"
        value={sku.color_system_id}
        onChange={(e) => onChange({ ...sku, color_system_id: e.target.value })}
      />
      <input
        className="rounded border border-gray-300 px-2 py-1"
        placeholder="カラー"
        value={sku.color_code}
        onChange={(e) => onChange({ ...sku, color_code: e.target.value })}
      />
      <input
        className="rounded border border-gray-300 px-2 py-1"
        type="number"
        min={0}
        placeholder="店舗在庫"
        value={sku.store_stock}
        onChange={(e) => onChange({ ...sku, store_stock: Number(e.target.value) })}
      />
      <button type="button" onClick={onRemove} className="text-xs text-red-600 hover:underline">
        削除
      </button>
    </div>
  );
}

function CreateProductForm() {
  const [productId, setProductId] = useState("");
  const [productName, setProductName] = useState("");
  const [category, setCategory] = useState("");
  const [defaultPrice, setDefaultPrice] = useState("1000");
  const [skus, setSkus] = useState<SkuInput[]>([{ ...emptySku }]);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function updateSku(index: number, next: SkuInput) {
    setSkus((prev) => prev.map((s, i) => (i === index ? next : s)));
  }

  function removeSku(index: number) {
    setSkus((prev) => prev.filter((_, i) => i !== index));
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    setMessage(null);
    try {
      const payload: ProductCreateRequest = {
        product_id: productId,
        product_name: productName,
        category,
        default_price: Number(defaultPrice),
        skus: skus.filter((s) => s.sku_id && s.barcode_ean13),
      };
      const response = await apiClient.post<ProductResponse>("/admin/products", payload);
      setMessage(`商品「${response.data.product_name}」を登録しました（SKU ${response.data.skus.length}件）。`);
      setProductId("");
      setProductName("");
      setCategory("");
      setDefaultPrice("1000");
      setSkus([{ ...emptySku }]);
    } catch (err) {
      setError(getErrorMessage(err, "商品登録に失敗しました。"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card>
      <h2 className="mb-3 text-lg font-semibold">新規商品登録</h2>
      <form onSubmit={handleSubmit}>
        <div className="grid grid-cols-2 gap-3">
          <Field label="商品ID" htmlFor="new-product-id">
            <TextInput
              id="new-product-id"
              value={productId}
              onChange={(e) => setProductId(e.target.value)}
              required
            />
          </Field>
          <Field label="商品名" htmlFor="new-product-name">
            <TextInput
              id="new-product-name"
              value={productName}
              onChange={(e) => setProductName(e.target.value)}
              required
            />
          </Field>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field label="カテゴリ" htmlFor="new-product-category">
            <TextInput
              id="new-product-category"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              required
            />
          </Field>
          <Field label="定価（円）" htmlFor="new-product-price">
            <TextInput
              id="new-product-price"
              type="number"
              min={0}
              value={defaultPrice}
              onChange={(e) => setDefaultPrice(e.target.value)}
              required
            />
          </Field>
        </div>

        <div className="mb-3">
          <div className="mb-1 flex items-center justify-between">
            <span className="text-sm font-medium text-gray-700">SKU（サイズ・カラー展開）</span>
            <button
              type="button"
              onClick={() => setSkus((prev) => [...prev, { ...emptySku, sku_id: "", barcode_ean13: "" }])}
              className="text-xs text-blue-600 hover:underline"
            >
              + SKU追加
            </button>
          </div>
          <p className="mb-2 text-xs text-gray-500">
            サイズ体系・カラー体系は事前登録済みの参照データを指定してください（初期構築時のシード:
            サイズ体系 STANDARD / カラー体系 BASIC）。
          </p>
          {skus.map((sku, index) => (
            <SkuRow
              key={index}
              sku={sku}
              onChange={(next) => updateSku(index, next)}
              onRemove={() => removeSku(index)}
            />
          ))}
        </div>

        {error && <ErrorBanner message={error} />}
        {message && <SuccessBanner message={message} />}
        <Button type="submit" disabled={submitting}>
          {submitting ? "登録中..." : "登録"}
        </Button>
      </form>
    </Card>
  );
}

function UpdateProductForm() {
  const [productId, setProductId] = useState("");
  const [product, setProduct] = useState<ProductResponse | null>(null);
  const [lookupError, setLookupError] = useState<string | null>(null);

  const [productName, setProductName] = useState("");
  const [category, setCategory] = useState("");
  const [defaultPrice, setDefaultPrice] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [newSkus, setNewSkus] = useState<SkuInput[]>([]);

  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleLookup(event: React.FormEvent) {
    event.preventDefault();
    setLookupError(null);
    setProduct(null);
    setMessage(null);
    const id = productId.trim();
    if (!id) return;
    try {
      const response = await apiClient.get<ProductResponse>(`/products/${encodeURIComponent(id)}`);
      setProduct(response.data);
      setProductName(response.data.product_name);
      setCategory(response.data.category);
      setDefaultPrice(String(response.data.default_price));
      setIsActive(response.data.is_active);
      setNewSkus([]);
    } catch (err) {
      setLookupError(getErrorMessage(err, "商品が見つかりませんでした。"));
    }
  }

  function updateNewSku(index: number, next: SkuInput) {
    setNewSkus((prev) => prev.map((s, i) => (i === index ? next : s)));
  }

  function removeNewSku(index: number) {
    setNewSkus((prev) => prev.filter((_, i) => i !== index));
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!product) return;
    setSubmitting(true);
    setError(null);
    setMessage(null);
    try {
      const payload: ProductUpdateRequest = {
        product_name: productName,
        category,
        default_price: Number(defaultPrice),
        is_active: isActive,
        skus: newSkus.filter((s) => s.sku_id && s.barcode_ean13),
      };
      const response = await apiClient.put<ProductResponse>(
        `/admin/products/${encodeURIComponent(product.product_id)}`,
        payload
      );
      setProduct(response.data);
      setNewSkus([]);
      setMessage("商品情報を更新しました。");
    } catch (err) {
      setError(getErrorMessage(err, "更新に失敗しました。"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card>
      <h2 className="mb-3 text-lg font-semibold">商品情報の更新 / SKU追加</h2>
      <form onSubmit={handleLookup} className="mb-4 flex gap-2">
        <TextInput
          value={productId}
          onChange={(e) => setProductId(e.target.value)}
          placeholder="商品ID"
        />
        <Button type="submit" variant="secondary">
          呼び出し
        </Button>
      </form>
      {lookupError && <p className="mb-3 text-sm text-red-600">{lookupError}</p>}

      {product && (
        <form onSubmit={handleSubmit}>
          <Field label="商品名" htmlFor="edit-product-name">
            <TextInput
              id="edit-product-name"
              value={productName}
              onChange={(e) => setProductName(e.target.value)}
              required
            />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="カテゴリ" htmlFor="edit-product-category">
              <TextInput
                id="edit-product-category"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                required
              />
            </Field>
            <Field label="定価（円）" htmlFor="edit-product-price">
              <TextInput
                id="edit-product-price"
                type="number"
                min={0}
                value={defaultPrice}
                onChange={(e) => setDefaultPrice(e.target.value)}
                required
              />
            </Field>
          </div>
          <label className="mb-3 flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={isActive}
              onChange={(e) => setIsActive(e.target.checked)}
            />
            有効
          </label>

          <div className="mb-3">
            <p className="mb-1 text-sm font-medium text-gray-700">
              既存SKU（{product.skus.length}件、在庫変更は在庫画面から行ってください）
            </p>
            <ul className="mb-3 space-y-1 text-xs text-gray-600">
              {product.skus.map((sku) => (
                <li key={sku.sku_id}>
                  {sku.sku_id}（{sku.size_code}/{sku.color_code}） 店舗:{sku.store_stock} 倉庫:
                  {sku.warehouse_stock}
                </li>
              ))}
            </ul>

            <div className="mb-1 flex items-center justify-between">
              <span className="text-sm font-medium text-gray-700">新規SKUを追加</span>
              <button
                type="button"
                onClick={() => setNewSkus((prev) => [...prev, { ...emptySku, sku_id: "", barcode_ean13: "" }])}
                className="text-xs text-blue-600 hover:underline"
              >
                + SKU追加
              </button>
            </div>
            {newSkus.map((sku, index) => (
              <SkuRow
                key={index}
                sku={sku}
                onChange={(next) => updateNewSku(index, next)}
                onRemove={() => removeNewSku(index)}
              />
            ))}
          </div>

          {error && <ErrorBanner message={error} />}
          {message && <SuccessBanner message={message} />}
          <Button type="submit" disabled={submitting}>
            {submitting ? "保存中..." : "保存"}
          </Button>
        </form>
      )}
    </Card>
  );
}

function ProductsAdminContent() {
  return (
    <div className="space-y-6">
      <CreateProductForm />
      <UpdateProductForm />
    </div>
  );
}

export default function AdminProductsPage() {
  return (
    <RoleGate allow={["MANAGER", "ADMIN"]}>
      <ProductsAdminContent />
    </RoleGate>
  );
}
