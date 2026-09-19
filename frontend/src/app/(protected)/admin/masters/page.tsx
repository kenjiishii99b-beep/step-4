"use client";

import { useState } from "react";

import { RoleGate } from "@/components/RoleGate";
import { Button, Card, ErrorBanner, Field, Select, SuccessBanner, TextInput } from "@/components/ui";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { getErrorMessage } from "@/lib/errors";
import {
  DiscountResponse,
  DiscountTargetType,
  DiscountType,
  DiscountUpsertRequest,
  TaxRateResponse,
  TaxRateUpsertRequest,
} from "@/types/api";

const emptyDiscountForm: DiscountUpsertRequest = {
  discount_id: "",
  target_type: "SKU",
  product_id: "",
  sku_id: "",
  discount_type: "RATE",
  discount_value: "0",
  valid_from: "",
  valid_to: "",
  priority: 1,
  is_active: true,
};

function DiscountForm() {
  const [form, setForm] = useState<DiscountUpsertRequest>(emptyDiscountForm);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    setMessage(null);
    try {
      const payload: DiscountUpsertRequest = {
        ...form,
        product_id: form.target_type === "PRODUCT" ? form.product_id : null,
        sku_id: form.target_type === "SKU" ? form.sku_id : null,
        valid_to: form.valid_to || null,
      };
      const response = await apiClient.put<DiscountResponse>("/masters/discounts", payload);
      setMessage(`値引き「${response.data.discount_id}」を保存しました。`);
    } catch (err) {
      setError(getErrorMessage(err, "保存に失敗しました。"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card>
      <h2 className="mb-3 text-lg font-semibold">値引きマスター登録・更新</h2>
      <form onSubmit={handleSubmit}>
        <Field label="値引きID" htmlFor="discount-id">
          <TextInput
            id="discount-id"
            value={form.discount_id}
            onChange={(e) => setForm((f) => ({ ...f, discount_id: e.target.value }))}
            required
          />
        </Field>
        <Field label="適用対象" htmlFor="discount-target">
          <Select
            id="discount-target"
            value={form.target_type}
            onChange={(e) =>
              setForm((f) => ({ ...f, target_type: e.target.value as DiscountTargetType }))
            }
          >
            <option value="SKU">SKU単位</option>
            <option value="PRODUCT">商品単位</option>
            <option value="MEMBER">会員向け（全体）</option>
          </Select>
        </Field>
        {form.target_type === "SKU" && (
          <Field label="SKU ID" htmlFor="discount-sku">
            <TextInput
              id="discount-sku"
              value={form.sku_id ?? ""}
              onChange={(e) => setForm((f) => ({ ...f, sku_id: e.target.value }))}
              required
            />
          </Field>
        )}
        {form.target_type === "PRODUCT" && (
          <Field label="商品ID" htmlFor="discount-product">
            <TextInput
              id="discount-product"
              value={form.product_id ?? ""}
              onChange={(e) => setForm((f) => ({ ...f, product_id: e.target.value }))}
              required
            />
          </Field>
        )}
        <div className="grid grid-cols-2 gap-3">
          <Field label="値引き種別" htmlFor="discount-type">
            <Select
              id="discount-type"
              value={form.discount_type}
              onChange={(e) =>
                setForm((f) => ({ ...f, discount_type: e.target.value as DiscountType }))
              }
            >
              <option value="RATE">割合（%）</option>
              <option value="AMOUNT">金額（円/個）</option>
            </Select>
          </Field>
          <Field label="値引き値" htmlFor="discount-value">
            <TextInput
              id="discount-value"
              type="number"
              step="0.01"
              min={0}
              value={form.discount_value}
              onChange={(e) => setForm((f) => ({ ...f, discount_value: e.target.value }))}
              required
            />
          </Field>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field label="適用開始日時" htmlFor="discount-valid-from">
            <TextInput
              id="discount-valid-from"
              type="datetime-local"
              value={form.valid_from}
              onChange={(e) => setForm((f) => ({ ...f, valid_from: e.target.value }))}
              required
            />
          </Field>
          <Field label="適用終了日時（任意）" htmlFor="discount-valid-to">
            <TextInput
              id="discount-valid-to"
              type="datetime-local"
              value={form.valid_to ?? ""}
              onChange={(e) => setForm((f) => ({ ...f, valid_to: e.target.value }))}
            />
          </Field>
        </div>
        <Field label="優先度（数値が小さいほど優先）" htmlFor="discount-priority">
          <TextInput
            id="discount-priority"
            type="number"
            value={form.priority}
            onChange={(e) => setForm((f) => ({ ...f, priority: Number(e.target.value) }))}
            required
          />
        </Field>
        <label className="mb-3 flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={form.is_active}
            onChange={(e) => setForm((f) => ({ ...f, is_active: e.target.checked }))}
          />
          有効
        </label>
        {error && <ErrorBanner message={error} />}
        {message && <SuccessBanner message={message} />}
        <Button type="submit" disabled={submitting}>
          {submitting ? "保存中..." : "保存"}
        </Button>
      </form>
    </Card>
  );
}

const emptyTaxForm: TaxRateUpsertRequest = {
  tax_rate_id: "",
  tax_rate: "10.00",
  valid_from: "",
  valid_to: "",
  is_active: true,
};

function TaxRateForm() {
  const [form, setForm] = useState<TaxRateUpsertRequest>(emptyTaxForm);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    setMessage(null);
    try {
      const payload: TaxRateUpsertRequest = { ...form, valid_to: form.valid_to || null };
      const response = await apiClient.put<TaxRateResponse>("/masters/tax-rates", payload);
      setMessage(`税率「${response.data.tax_rate_id}」を保存しました。`);
    } catch (err) {
      setError(getErrorMessage(err, "保存に失敗しました。"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card>
      <h2 className="mb-3 text-lg font-semibold">税率マスター登録・更新</h2>
      <form onSubmit={handleSubmit}>
        <Field label="税率ID" htmlFor="tax-id">
          <TextInput
            id="tax-id"
            value={form.tax_rate_id}
            onChange={(e) => setForm((f) => ({ ...f, tax_rate_id: e.target.value }))}
            required
          />
        </Field>
        <Field label="税率（%）" htmlFor="tax-rate">
          <TextInput
            id="tax-rate"
            type="number"
            step="0.01"
            min={0}
            max={100}
            value={form.tax_rate}
            onChange={(e) => setForm((f) => ({ ...f, tax_rate: e.target.value }))}
            required
          />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="適用開始日時" htmlFor="tax-valid-from">
            <TextInput
              id="tax-valid-from"
              type="datetime-local"
              value={form.valid_from}
              onChange={(e) => setForm((f) => ({ ...f, valid_from: e.target.value }))}
              required
            />
          </Field>
          <Field label="適用終了日時（任意）" htmlFor="tax-valid-to">
            <TextInput
              id="tax-valid-to"
              type="datetime-local"
              value={form.valid_to ?? ""}
              onChange={(e) => setForm((f) => ({ ...f, valid_to: e.target.value }))}
            />
          </Field>
        </div>
        <label className="mb-3 flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={form.is_active}
            onChange={(e) => setForm((f) => ({ ...f, is_active: e.target.checked }))}
          />
          有効
        </label>
        {error && <ErrorBanner message={error} />}
        {message && <SuccessBanner message={message} />}
        <Button type="submit" disabled={submitting}>
          {submitting ? "保存中..." : "保存"}
        </Button>
      </form>
    </Card>
  );
}

function MastersContent() {
  const { session } = useAuth();
  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
      <DiscountForm />
      {session?.role === "ADMIN" ? (
        <TaxRateForm />
      ) : (
        <Card>
          <p className="text-sm text-gray-500">税率マスターの変更はシステム管理者のみ実行できます。</p>
        </Card>
      )}
    </div>
  );
}

export default function AdminMastersPage() {
  return (
    <RoleGate allow={["MANAGER", "ADMIN"]}>
      <MastersContent />
    </RoleGate>
  );
}
