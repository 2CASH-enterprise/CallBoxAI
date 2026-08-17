import type { Metadata } from "next";
import { Space_Grotesk, Inter, IBM_Plex_Mono } from "next/font/google";
import { AuthProvider } from "@/lib/AuthContext";
import { OrganizationProvider } from "@/lib/OrganizationContext";
import { AppShell } from "@/components/AppShell";
import "./globals.css";

const display = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-display",
  weight: ["500", "600", "700"],
});
const body = Inter({ subsets: ["latin"], variable: "--font-body" });
const mono = IBM_Plex_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: "CallBoxAI — Tableau de bord",
  description: "Plateforme d'agents IA vocaux pour l'Afrique francophone",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr" className={`${display.variable} ${body.variable} ${mono.variable}`}>
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
