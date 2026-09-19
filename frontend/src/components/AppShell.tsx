"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { useAuth } from "@/lib/auth-context";
import { Role } from "@/types/auth";

interface NavItem {
  href: string;
  label: string;
  roles?: Role[];
}

const NAV_ITEMS: NavItem[] = [
  { href: "/pos", label: "会計" },
  { href: "/pos/refund-exchange", label: "返品・交換" },
  { href: "/inventory", label: "在庫" },
  { href: "/members", label: "会員" },
  { href: "/admin/masters", label: "値引き・税率", roles: ["MANAGER", "ADMIN"] },
  { href: "/admin/products", label: "商品登録", roles: ["MANAGER", "ADMIN"] },
  { href: "/admin/staff", label: "スタッフ管理", roles: ["ADMIN"] },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const { session, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  async function handleLogout() {
    await logout();
    router.replace("/login");
  }

  const visibleItems = NAV_ITEMS.filter(
    (item) => !item.roles || (session && item.roles.includes(session.role))
  );

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="border-b border-gray-200 bg-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
          <span className="text-base font-semibold text-gray-900">Apparel POS</span>
          <nav className="flex flex-wrap gap-1 text-sm">
            {visibleItems.map((item) => {
              const active = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`rounded px-3 py-1.5 ${
                    active
                      ? "bg-blue-600 text-white"
                      : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
                  }`}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
          <div className="ml-auto flex items-center gap-3 text-sm text-gray-600">
            {session && (
              <span>
                {session.staff_name}（{session.role}）
              </span>
            )}
            <button
              onClick={handleLogout}
              className="rounded border border-gray-300 px-3 py-1.5 text-gray-700 hover:bg-gray-100"
            >
              ログアウト
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
    </div>
  );
}
