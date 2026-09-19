"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/lib/auth-context";

export default function HomePage() {
  const { session, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (isLoading) return;
    router.replace(session ? "/pos" : "/login");
  }, [isLoading, session, router]);

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-2 p-24">
      <p className="text-sm text-gray-500">読み込み中...</p>
    </main>
  );
}
