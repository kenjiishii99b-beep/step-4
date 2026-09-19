"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { RoleGate } from "@/components/RoleGate";
import { Button, Card, ErrorBanner, Field, Select, SuccessBanner, TextInput } from "@/components/ui";
import { apiClient } from "@/lib/api-client";
import { getErrorMessage } from "@/lib/errors";
import { Role } from "@/types/auth";
import { Staff, StaffListResponse, StaffUpsertRequest } from "@/types/api";

const PAGE_SIZE = 20;

const emptyForm: StaffUpsertRequest = {
  staff_id: "",
  staff_name: "",
  role: "STAFF",
  is_active: true,
  password: "",
};

function StaffAdminContent() {
  const queryClient = useQueryClient();
  const [roleFilter, setRoleFilter] = useState<Role | "">("");
  const [activeFilter, setActiveFilter] = useState<"" | "true" | "false">("");
  const [offset, setOffset] = useState(0);

  const [form, setForm] = useState<StaffUpsertRequest>(emptyForm);
  const [isEditing, setIsEditing] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const listQuery = useQuery({
    queryKey: ["admin-staff-list", roleFilter, activeFilter, offset],
    queryFn: async () => {
      const params: Record<string, string | number> = { limit: PAGE_SIZE, offset };
      if (roleFilter) params.role = roleFilter;
      if (activeFilter) params.is_active = activeFilter;
      const response = await apiClient.get<StaffListResponse>("/admin/staff", { params });
      return response.data;
    },
  });

  function startCreate() {
    setForm(emptyForm);
    setIsEditing(false);
    setSaveError(null);
    setSaveMessage(null);
  }

  function startEdit(staff: Staff) {
    setForm({
      staff_id: staff.staff_id,
      staff_name: staff.staff_name,
      role: staff.role,
      is_active: staff.is_active,
      password: "",
    });
    setIsEditing(true);
    setSaveError(null);
    setSaveMessage(null);
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    setSaveError(null);
    setSaveMessage(null);
    try {
      const payload: StaffUpsertRequest = { ...form };
      if (!payload.password) {
        delete payload.password;
      }
      await apiClient.post<Staff>("/admin/staff", payload);
      setSaveMessage(isEditing ? "スタッフ情報を更新しました。" : "スタッフを新規作成しました。");
      await queryClient.invalidateQueries({ queryKey: ["admin-staff-list"] });
      startCreate();
    } catch (err) {
      setSaveError(getErrorMessage(err, "保存に失敗しました。"));
    } finally {
      setSaving(false);
    }
  }

  const staffList = listQuery.data;

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
      <div className="lg:col-span-2">
        <Card>
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-lg font-semibold">スタッフ一覧</h2>
            <Button type="button" variant="secondary" onClick={startCreate}>
              新規作成
            </Button>
          </div>

          <div className="mb-3 flex flex-wrap gap-3">
            <Select
              value={roleFilter}
              onChange={(e) => {
                setOffset(0);
                setRoleFilter(e.target.value as Role | "");
              }}
              className="w-auto"
            >
              <option value="">全ロール</option>
              <option value="STAFF">STAFF</option>
              <option value="MANAGER">MANAGER</option>
              <option value="ADMIN">ADMIN</option>
            </Select>
            <Select
              value={activeFilter}
              onChange={(e) => {
                setOffset(0);
                setActiveFilter(e.target.value as "" | "true" | "false");
              }}
              className="w-auto"
            >
              <option value="">有効/無効すべて</option>
              <option value="true">有効のみ</option>
              <option value="false">無効のみ</option>
            </Select>
          </div>

          {listQuery.isLoading && <p className="text-sm text-gray-500">読み込み中...</p>}
          {listQuery.isError && (
            <ErrorBanner message={getErrorMessage(listQuery.error, "一覧の取得に失敗しました。")} />
          )}

          {staffList && (
            <>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-gray-500">
                    <th className="py-2">ID</th>
                    <th className="py-2">氏名</th>
                    <th className="py-2">ロール</th>
                    <th className="py-2">状態</th>
                    <th className="py-2"></th>
                  </tr>
                </thead>
                <tbody>
                  {staffList.items.map((staff) => (
                    <tr key={staff.staff_id} className="border-b last:border-0">
                      <td className="py-2 font-mono text-xs">{staff.staff_id}</td>
                      <td className="py-2">{staff.staff_name}</td>
                      <td className="py-2">{staff.role}</td>
                      <td className="py-2">{staff.is_active ? "有効" : "無効"}</td>
                      <td className="py-2">
                        <button
                          onClick={() => startEdit(staff)}
                          className="text-xs text-blue-600 hover:underline"
                        >
                          編集
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="mt-3 flex items-center justify-between text-sm text-gray-500">
                <span>
                  {staffList.total}件中 {offset + 1}〜{Math.min(offset + PAGE_SIZE, staffList.total)}件
                </span>
                <div className="flex gap-2">
                  <Button
                    type="button"
                    variant="secondary"
                    disabled={offset === 0}
                    onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}
                  >
                    前へ
                  </Button>
                  <Button
                    type="button"
                    variant="secondary"
                    disabled={offset + PAGE_SIZE >= staffList.total}
                    onClick={() => setOffset((o) => o + PAGE_SIZE)}
                  >
                    次へ
                  </Button>
                </div>
              </div>
            </>
          )}
        </Card>
      </div>

      <Card>
        <h2 className="mb-3 text-lg font-semibold">{isEditing ? "スタッフ編集" : "新規作成"}</h2>
        <form onSubmit={handleSubmit}>
          <Field label="スタッフID" htmlFor="staff-id">
            <TextInput
              id="staff-id"
              value={form.staff_id}
              onChange={(e) => setForm((f) => ({ ...f, staff_id: e.target.value }))}
              disabled={isEditing}
              required
            />
          </Field>
          <Field label="氏名" htmlFor="staff-name">
            <TextInput
              id="staff-name"
              value={form.staff_name}
              onChange={(e) => setForm((f) => ({ ...f, staff_name: e.target.value }))}
              required
            />
          </Field>
          <Field label="ロール" htmlFor="staff-role">
            <Select
              id="staff-role"
              value={form.role}
              onChange={(e) => setForm((f) => ({ ...f, role: e.target.value as Role }))}
            >
              <option value="STAFF">STAFF</option>
              <option value="MANAGER">MANAGER</option>
              <option value="ADMIN">ADMIN</option>
            </Select>
          </Field>
          <label className="mb-3 flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(e) => setForm((f) => ({ ...f, is_active: e.target.checked }))}
            />
            有効
          </label>
          <Field
            label={isEditing ? "パスワード（変更する場合のみ入力）" : "パスワード"}
            htmlFor="staff-password"
          >
            <TextInput
              id="staff-password"
              type="password"
              value={form.password ?? ""}
              onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
              required={!isEditing}
              minLength={8}
            />
          </Field>
          {saveError && <ErrorBanner message={saveError} />}
          {saveMessage && <SuccessBanner message={saveMessage} />}
          <Button type="submit" disabled={saving}>
            {saving ? "保存中..." : "保存"}
          </Button>
        </form>
      </Card>
    </div>
  );
}

export default function AdminStaffPage() {
  return (
    <RoleGate allow={["ADMIN"]}>
      <StaffAdminContent />
    </RoleGate>
  );
}
