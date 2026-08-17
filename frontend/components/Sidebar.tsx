"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import styles from "./Sidebar.module.css";

const links = [
  { href: "/dashboard", label: "Tableau de bord" },
  { href: "/agents", label: "Agents IA" },
  { href: "/calls", label: "Appels" },
  { href: "/contacts", label: "Contacts (CRM)" },
];

const adminLinks = [{ href: "/distributors", label: "Distributeurs" }];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className={styles.sidebar}>
      <div className={styles.brand}>
        <span className={styles.brandMark}>●</span>
        <span className={styles.brandName}>CallBoxAI</span>
      </div>

      <div className={styles.navLabel}>Opérations</div>
      <nav className={styles.nav}>
        {links.map((link) => {
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
        })}
      </nav>

      <div className={styles.navLabel}>Pilotage</div>
      <nav className={styles.nav}>
        {adminLinks.map((link) => {
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
        })}
      </nav>

      <div className={styles.footer}>
        Environnement : mock<br />
        v0.1.0
      </div>
    </aside>
  );
}
