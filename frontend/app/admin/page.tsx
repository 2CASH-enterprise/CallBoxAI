"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/AuthContext";
import { api, AdminDashboard } from "@/lib/api";
import { KpiCard } from "@/components/KpiCard";
import styles from "./admin.module.css";

export default function AdminPage() {
  const { user } = useAuth();
  const router = useRouter();
  const [dashboard, setDashboard] = useState<AdminDashboard | null>(null);
  const [loading, setLoading] = useState(true);

  // Garde-fou : réservé au Super Admin (contrairement à /distributors, un
  // Distributeur ne doit jamais voir la vue plateforme complète).
  useEffect(() => {
    if (user && !user.is_super_admin) {
      router.replace("/dashboard");
    }
  }, [user, router]);

  useEffect(() => {
    if (!user?.is_super_admin) return;
    setLoading(true);
    api.getAdminDashboard().then(setDashboard).finally(() => setLoading(false));
  }, [user]);

  if (!user?.is_super_admin) return null;

  if (loading || !dashboard) {
    return <p style={{ color: "var(--color-muted)" }}>Chargement…</p>;
  }

  const { totals } = dashboard;

  return (
    <div>
      <div className={styles.header}>
        <h1 className={styles.title}>Vue plateforme</h1>
        <p className={styles.subtitle}>Ensemble des entreprises, distributeurs et activité, tous portefeuilles confondus.</p>
      </div>

      <div className={styles.grid}>
        <KpiCard label="Entreprises clientes" value={totals.organizations} />
        <KpiCard label="Distributeurs" value={totals.distributors} />
        <KpiCard label="Agents IA" value={totals.agents} />
        <KpiCard label="Comptes utilisateurs" value={totals.users} />
      </div>

      <div className={styles.splitGrid}>
        <KpiCard label="Appels (total)" value={totals.calls_total} />
        <KpiCard label="Appels aujourd'hui" value={totals.calls_today} />
        <KpiCard
          label={`Revenu estimé (${dashboard.current_period})`}
          value={`${dashboard.estimated_revenue_current_period.toLocaleString("fr-FR")} FCFA`}
        />
        <KpiCard
          label="Commissions dues (estimé)"
          value={`${dashboard.estimated_commissions_current_period.toLocaleString("fr-FR")} FCFA`}
        />
      </div>

      <div className={styles.section}>
        <div className={styles.sectionHeader}>Répartition du portefeuille</div>
        <div className={styles.row} style={{ gridTemplateColumns: "1fr 1fr" }}>
          <span>Clients directs</span>
          <span>{totals.organizations_direct}</span>
        </div>
        <div className={styles.row} style={{ gridTemplateColumns: "1fr 1fr" }}>
          <span>Clients apportés par un distributeur</span>
          <span>{totals.organizations_via_distributor}</span>
        </div>
      </div>

      <div className={styles.section}>
        <div className={styles.sectionHeader}>Distributeurs</div>
        <div className={`${styles.distRow} ${styles.rowHead}`}>
          <span>Nom</span>
          <span>Taux</span>
          <span>Clients</span>
          <span>Appels</span>
        </div>
        {dashboard.distributors.length === 0 ? (
          <div className={styles.emptyState}>Aucun distributeur pour l'instant.</div>
        ) : (
          dashboard.distributors.map((d) => (
            <div key={d.id} className={styles.distRow}>
              <span>{d.name}</span>
              <span style={{ fontFamily: "var(--font-mono)", color: "var(--color-amber)" }}>{d.commission_rate}%</span>
              <span>{d.clients_count}</span>
              <span>{d.calls_count}</span>
            </div>
          ))
        )}
      </div>

      <div className={styles.section}>
        <div className={styles.sectionHeader}>Entreprises clientes (20 plus récentes)</div>
        <div className={`${styles.row} ${styles.rowHead}`}>
          <span>Nom</span>
          <span>Origine</span>
          <span>Agents</span>
          <span>Appels</span>
          <span>Créée le</span>
        </div>
        {dashboard.organizations.length === 0 ? (
          <div className={styles.emptyState}>Aucune entreprise pour l'instant.</div>
        ) : (
          dashboard.organizations.map((o) => (
            <div key={o.id} className={styles.row}>
              <span>{o.name}</span>
              <span>
                {o.distributor_name ? (
                  <span className={`${styles.badge} ${styles.badgeDistributor}`}>{o.distributor_name}</span>
                ) : (
                  <span className={`${styles.badge} ${styles.badgeDirect}`}>Direct</span>
                )}
              </span>
              <span>{o.agents_count}</span>
              <span>{o.calls_count}</span>
              <span style={{ color: "var(--color-muted)", fontFamily: "var(--font-mono)", fontSize: 12 }}>
                {new Date(o.created_at).toLocaleDateString("fr-FR")}
              </span>
            </div>
          ))
        )}
      </div>

      <p className={styles.note}>
        Indicateurs business avancés (MRR, ARR, churn, ARPU) et monitoring technique (CPU, latence API, erreurs
        fournisseurs) disponibles une fois le moteur de facturation (sections 20-21) et l'observabilité Prometheus/Grafana
        (section 26) branchés — non affichés ici pour éviter tout chiffre approximatif.
      </p>
    </div>
  );
}
