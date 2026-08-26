"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard, Bot, Phone, Megaphone, BarChart3,
  BookOpen, Users, Globe, Network, Calendar, TrendingDown,
  MessageSquare, ClipboardList, LifeBuoy, MessageCircle, Sunrise, Inbox, type LucideIcon,
} from "lucide-react";
import { useAuth } from "@/lib/AuthContext";
import { useOrganization } from "@/lib/OrganizationContext";
import { useBranding } from "@/lib/useBranding";
import { api, Agent } from "@/lib/api";
import styles from "./Sidebar.module.css";

interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  // Prédicat de capacité (section 41) : décide si ce lien est actif ou
  // grisé selon les agents RÉELLEMENT configurés dans l'organisation.
  // Absent = toujours actif dès qu'au moins un agent existe (socle commun).
  isRelevant?: (agents: Agent[]) => boolean;
}

const SALES_CATEGORIES = ["prospection", "telecom"];

const clientLinks: NavItem[] = [
  { href: "/today", label: "Aujourd'hui", icon: Sunrise },
  { href: "/dashboard", label: "Tableau de bord", icon: LayoutDashboard },
  { href: "/agents", label: "Agents IA", icon: Bot },
  { href: "/calls", label: "Appels", icon: Phone },
  {
    href: "/messages", label: "Messages", icon: MessageSquare,
    isRelevant: (agents) => agents.some((a) => !!a.business_hours_start),
  },
  {
    href: "/sms", label: "SMS", icon: MessageCircle,
    isRelevant: (agents) => agents.some((a) => a.pms_enabled || a.kyc_enabled),
  },
  {
    href: "/tickets", label: "Tickets", icon: LifeBuoy,
    isRelevant: (agents) => agents.some((a) => a.ticketing_enabled),
  },
  { href: "/appointments", label: "Rendez-vous", icon: Calendar },
  {
    href: "/campaigns", label: "Campagnes", icon: Megaphone,
    isRelevant: (agents) => agents.some((a) => SALES_CATEGORIES.includes(a.category)),
  },
  { href: "/surveys", label: "Sondages", icon: ClipboardList },
  {
    href: "/pipeline", label: "Pipeline", icon: TrendingDown,
    isRelevant: (agents) => agents.some((a) => SALES_CATEGORIES.includes(a.category)),
  },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/knowledge", label: "Base de connaissances", icon: BookOpen },
  { href: "/contacts", label: "Contacts (CRM)", icon: Users },
];

export function Sidebar() {
  const pathname = usePathname();
  const { user } = useAuth();
  const { currentOrg } = useOrganization();
  const branding = useBranding();
  const [agents, setAgents] = useState<Agent[]>([]);

  useEffect(() => {
    if (!currentOrg) {
      setAgents([]);
      return;
    }
    api.listAgents(currentOrg.organization_id).then(setAgents).catch(() => setAgents([]));
  }, [currentOrg]);

  // Un utilisateur "client" (membre d'au moins une organisation) voit les
  // menus opérationnels. Un Super Admin ou un Distributeur voit "Pilotage".
  // Section 6.1 du cahier des charges : rôles plateforme vs rôles par entreprise.
  const showClientLinks = (user?.memberships.length || 0) > 0;
  const pilotageLinks: NavItem[] = [
    ...(user?.is_super_admin ? [{ href: "/admin", label: "Vue plateforme", icon: Globe }] : []),
    ...(user?.is_super_admin ? [{ href: "/admin/agent-requests", label: "Demandes d'agents", icon: Inbox }] : []),
    ...(user?.is_super_admin || user?.distributor_id
      ? [{ href: "/distributors", label: "Distributeurs", icon: Network }]
      : []),
  ];

  const renderLinks = (items: NavItem[]) =>
    items.map(({ href, label, icon: Icon, isRelevant }) => {
      const active = pathname?.startsWith(href);
      // Grisé (section 41) UNIQUEMENT si ce lien a un prédicat de capacité
      // ET qu'aucun agent existant ne le satisfait. Les liens sans
      // prédicat (Agents IA en particulier — il faut bien pouvoir y accéder
      // pour demander son tout premier agent !) ne sont jamais grisés.
      const isDisabled = isRelevant ? !isRelevant(agents) : false;

      if (isDisabled) {
        return (
          <span
            key={href}
            className={`${styles.navLink} ${styles.navLinkDisabled}`}
            title="Aucun agent actif n'utilise cette fonctionnalité"
          >
            <Icon size={16} strokeWidth={2} className={styles.navIcon} />
            <span>{label}</span>
          </span>
        );
      }

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
