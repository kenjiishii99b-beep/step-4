"use client";

import { useAuth } from "@/lib/auth-context";
import { Role } from "@/types/auth";

export function RoleGate({ allow, children }: { allow: Role[]; children: React.ReactNode }) {
  const { session } = useAuth();

  if (!session || !allow.includes(session.role)) {
    return (
      <div className="rounded border border-yellow-300 bg-yellow-50 p-4 text-sm text-yellow-800">
        このページを表示する権限がありません。
      </div>
    );
  }

  return <>{children}</>;
}
