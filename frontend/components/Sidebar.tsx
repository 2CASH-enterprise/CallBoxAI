"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard, Bot, Phone, Megaphone, BarChart3,
  BookOpen, Users, Globe, Network, Calendar, type LucideIcon,
} from "lucide-react";
import { useAuth } from "@/lib/AuthContext";
import { useBranding } from "@/lib/useBranding";
import styles from "./Sidebar.module.css";

interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

const clientLinks: NavItem[] = [
  { href: "/dashboard", label: "Tableau de bord", icon: LayoutDashboard },
  { href: "/agents", label: "Agents IA", icon: Bot },
  { href: "/calls", label: "Appels", icon: Phone },
  { href: "/appointments", label: "Rendez-vous", icon: Calendar },
  { href: "/campaigns", label: "Campagnes", icon: Megaphone },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/knowledge", label: "Base de connaissances", icon: BookOpen },
  { href: "/contacts", label: "Contacts (CRM)", icon: Users },
];

export function Sidebar() {
  const pathname = usePathname();
  const { user } = useAuth();
  const branding = useBranding();

  // Un utilisateur "client" (membre d'au moins une organisation) voit les
  // menus opérationnels. Un Super Admin ou un Distributeur voit "Pilotage".
  // Section 6.1 du cahier des charges : rôles plateforme vs rôles par entreprise.
  const showClientLinks = (user?.memberships.length || 0) > 0;
  const pilotageLinks: NavItem[] = [
    ...(user?.is_super_admin ? [{ href: "/admin", label: "Vue plateforme", icon: Globe }] : []),
    ...(user?.is_super_admin || user?.distributor_id
      ? [{ href: "/distributors", label: "Distributeurs", icon: Network }]
      : []),
  ];

  const renderLinks = (items: NavItem[]) =>
    items.map(({ href, label, icon: Icon }) => {
      const active = pathname?.startsWith(href);
      return (
        <Link key={href} href={href} className={`${styles.navLink} ${active ? styles.navLinkActive : ""}`}>
          <Icon size={16} strokeWidth={2} className={styles.navIcon} />
          <span>{label}</span>
        </Link>
      );
    });

  return (
    <aside className={styles.sidebar} style={{ ["--brand-color" as string]: branding.primaryColor }}>
      <div className={styles.brand}>
        {branding.logoUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={branding.logoUrl} alt={branding.name} className={styles.brandLogo} />
        ) : (
          <span className={styles.brandMark}>●</span>
        )}
        <span className={styles.brandName}>{branding.name}</span>
      </div>

      {showClientLinks && (
        <>
          <div className={styles.navLabel}>Opérations</div>
          <nav className={styles.nav}>{renderLinks(clientLinks)}</nav>
        </>
      )}

      {pilotageLinks.length > 0 && (
        <>
          <div className={styles.navLabel}>Pilotage</div>
          <nav className={styles.nav}>{renderLinks(pilotageLinks)}</nav>
        </>
      )}

      <div className={styles.footer}>
        <span className={styles.footerDot} />
        Environnement mock · v0.1.0
      </div>
    </aside>
  );
}
