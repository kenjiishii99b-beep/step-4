"use client";

import { useState } from "react";

import { Button, Card, ErrorBanner, Field, SuccessBanner, TextInput } from "@/components/ui";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { getErrorMessage } from "@/lib/errors";
import { Member, MemberUpsertRequest } from "@/types/api";

export default function MembersPage() {
  const { session } = useAuth();
  const canEdit = session?.role === "MANAGER" || session?.role === "ADMIN";

  const [memberId, setMemberId] = useState("");
  const [member, setMember] = useState<Member | null>(null);
  const [lookupError, setLookupError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);

  const [form, setForm] = useState<MemberUpsertRequest>({ member_name: "" });
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function handleLookup(event: React.FormEvent) {
    event.preventDefault();
    setLookupError(null);
    setSaveMessage(null);
    setMember(null);
    setNotFound(false);
    const id = memberId.trim();
    if (!id) return;
    try {
      const response = await apiClient.get<Member>(`/members/${encodeURIComponent(id)}`);
      setMember(response.data);
      setForm({
        member_name: response.data.member_name,
        phone_number: response.data.phone_number ?? "",
        address: response.data.address ?? "",
        gender: response.data.gender ?? "",
        age: response.data.age ?? undefined,
        point_balance: response.data.point_balance,
      });
    } catch (err) {
      setNotFound(true);
      setForm({ member_name: "" });
      setLookupError(getErrorMessage(err, "会員が見つかりませんでした。"));
    }
  }

  async function handleSave(event: React.FormEvent) {
    event.preventDefault();
    if (!canEdit) return;
    const id = memberId.trim();
    if (!id) {
      setSaveError("会員IDを入力してください。");
      return;
    }
    setSaving(true);
    setSaveError(null);
    setSaveMessage(null);
    try {
      const response = await apiClient.put<Member>(`/members/${encodeURIComponent(id)}`, {
        ...form,
        age: form.age === undefined || form.age === null ? undefined : Number(form.age),
        point_balance:
          form.point_balance === undefined || form.point_balance === null
            ? undefined
            : Number(form.point_balance),
      });
      setMember(response.data);
      setNotFound(false);
      setSaveMessage(member ? "会員情報を更新しました。" : "会員を新規登録しました。");
    } catch (err) {
      setSaveError(getErrorMessage(err, "保存に失敗しました。"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
      <Card>
        <h2 className="mb-3 text-lg font-semibold">会員照会</h2>
        <form onSubmit={handleLookup} className="flex gap-2">
          <TextInput
            value={memberId}
            onChange={(e) => setMemberId(e.target.value)}
            placeholder="会員ID"
          />
          <Button type="submit">照会</Button>
        </form>
        {lookupError && <p className="mt-2 text-sm text-red-600">{lookupError}</p>}
        {member && (
          <dl className="mt-4 space-y-1 text-sm">
            <div className="flex justify-between">
              <dt className="text-gray-500">氏名</dt>
              <dd>{member.member_name}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">電話番号</dt>
              <dd>{member.phone_number ?? "-"}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">住所</dt>
              <dd>{member.address ?? "-"}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">性別</dt>
              <dd>{member.gender ?? "-"}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">年齢</dt>
              <dd>{member.age ?? "-"}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">保有ポイント</dt>
              <dd>{member.point_balance}</dd>
            </div>
          </dl>
        )}
      </Card>

      {canEdit ? (
        <Card>
          <h2 className="mb-3 text-lg font-semibold">
            {notFound ? "会員を新規登録" : "会員情報を編集"}
          </h2>
          {notFound && (
            <p className="mb-3 text-sm text-gray-500">
              会員ID「{memberId}」は未登録です。内容を入力して登録できます。
            </p>
          )}
          <form onSubmit={handleSave}>
            <Field label="氏名" htmlFor="member-name">
              <TextInput
                id="member-name"
                value={form.member_name}
                onChange={(e) => setForm((f) => ({ ...f, member_name: e.target.value }))}
                required
              />
            </Field>
            <Field label="電話番号" htmlFor="member-phone">
              <TextInput
                id="member-phone"
                value={form.phone_number ?? ""}
                onChange={(e) => setForm((f) => ({ ...f, phone_number: e.target.value }))}
              />
            </Field>
            <Field label="住所" htmlFor="member-address">
              <TextInput
                id="member-address"
                value={form.address ?? ""}
                onChange={(e) => setForm((f) => ({ ...f, address: e.target.value }))}
              />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="性別" htmlFor="member-gender">
                <TextInput
                  id="member-gender"
                  value={form.gender ?? ""}
                  onChange={(e) => setForm((f) => ({ ...f, gender: e.target.value }))}
                />
              </Field>
              <Field label="年齢" htmlFor="member-age">
                <TextInput
                  id="member-age"
                  type="number"
                  min={0}
                  value={form.age ?? ""}
                  onChange={(e) =>
                    setForm((f) => ({
                      ...f,
                      age: e.target.value === "" ? undefined : Number(e.target.value),
                    }))
                  }
                />
              </Field>
            </div>
            <Field label="保有ポイント" htmlFor="member-points">
              <TextInput
                id="member-points"
                type="number"
                min={0}
                value={form.point_balance ?? ""}
                onChange={(e) =>
                  setForm((f) => ({
                    ...f,
                    point_balance: e.target.value === "" ? undefined : Number(e.target.value),
                  }))
                }
              />
            </Field>
            {saveError && <ErrorBanner message={saveError} />}
            {saveMessage && <SuccessBanner message={saveMessage} />}
            <Button type="submit" disabled={saving}>
              {saving ? "保存中..." : "保存"}
            </Button>
          </form>
        </Card>
      ) : (
        <Card>
          <p className="text-sm text-gray-500">
            会員情報の編集・新規登録は店長・システム管理者のみ実行できます。
          </p>
        </Card>
      )}
    </div>
  );
}
