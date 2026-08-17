"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/AuthContext";
import { useBranding } from "@/lib/useBranding";
import styles from "./Sidebar.module.css";

const clientLinks = [
  { href: "/dashboard", label: "Tableau de bord" },
  { href: "/agents", label: "Agents IA" },
  { href: "/calls", label: "Appels" },
  { href: "/contacts", label: "Contacts (CRM)" },
];

const pilotageLinks = [{ href: "/distributors", label: "Distributeurs" }];

export function Sidebar() {
  const pathname = usePathname();
  const { user } = useAuth();
  const branding = useBranding();

  // Un utilisateur "client" (membre d'au moins une organisation) voit les
  // menus opérationnels. Un Super Admin ou un Distributeur voit "Pilotage".
  // Section 6.1 du cahier des charges : rôles plateforme vs rôles par entreprise.
  const showClientLinks = (user?.memberships.length || 0) > 0;
  const pilotageLinks = [
    ...(user?.is_super_admin ? [{ href: "/admin", label: "Vue plateforme" }] : []),
    ...(user?.is_super_admin || user?.distributor_id ? [{ href: "/distributors", label: "Distributeurs" }] : []),
  ];

  const renderLinks = (items: typeof clientLinks) =>
    items.map((link) => {
      const active = pathname?.startsWith(link.href);
      return (
        <Link
          key={link.href}
          href={link.href}
          className={`${styles.navLink} ${active ? styles.navLinkActive : ""}`}
        >
          {link.label}
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
        Environnement : mock<br />
        v0.1.0
      </div>
    </aside>
  );
}
