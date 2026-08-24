"use client";

import { usePathname } from "next/navigation";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";
import { useAuth } from "@/lib/AuthContext";

const PUBLIC_PATHS = ["/", "/login", "/register"];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { loading } = useAuth();
  const isPublic = PUBLIC_PATHS.includes(pathname || "");

  if (isPublic) {
    return <>{children}</>;
  }

  if (loading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "100vh", color: "var(--color-muted)" }}>
        Chargement…
      </div>
    );
  }

  return (
    <div style={{ display: "flex", minHeight: "100vh" }}>
      <Sidebar />
      <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
        <TopBar />
        <main style={{ flex: 1, padding: "28px 32px" }}>{children}</main>
      </div>
    </div>
  );
}
