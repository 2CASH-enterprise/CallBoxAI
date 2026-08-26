import type { Metadata } from "next";
import { AuthProvider } from "@/lib/AuthContext";
import { OrganizationProvider } from "@/lib/OrganizationContext";
import { AppShell } from "@/components/AppShell";
import "./globals.css";

export const metadata: Metadata = {
  title: "CallBoxAI — Tableau de bord",
  description: "Un agent vocal IA qui répond à vos appels, en continu",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <body>
        <AuthProvider>
          <OrganizationProvider>
            <AppShell>{children}</AppShell>
          </OrganizationProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
