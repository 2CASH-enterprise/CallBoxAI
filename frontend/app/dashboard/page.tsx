"use client";

import { useEffect, useState } from "react";
import { useOrganization } from "@/lib/OrganizationContext";
import { api, Call, Agent } from "@/lib/api";
import { KpiCard } from "@/components/KpiCard";
import { Waveform } from "@/components/Waveform";
import styles from "./dashboard.module.css";

export default function DashboardPage() {
  const { currentOrg, loading: orgLoading } = useOrganization();
  const [calls, setCalls] = useState<Call[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!currentOrg) return;
    setLoading(true);
    Promise.all([api.listCalls(currentOrg.organization_id), api.listAgents(currentOrg.organization_id)])
      .then(([c, a]) => {
        setCalls(c);
        setAgents(a);
      })
      .finally(() => setLoading(false));
  }, [currentOrg]);

  if (orgLoading) {
    return <p className={styles.subtitle}>Chargement…</p>;
  }

  if (!currentOrg) {
    return (
      <div className={styles.section}>
        <div className={styles.emptyState}>
          Aucune organisation pour l'instant. Créez-en une depuis la barre du
          haut pour commencer.
        </div>
      </div>
    );
  }

  const inbound = calls.filter((c) => c.direction === "inbound").length;
  const outbound = calls.filter((c) => c.direction === "outbound").length;
  const completed = calls.filter((c) => c.status === "completed").length;
  const transferred = calls.filter((c) => c.status === "transferred").length;

  return (
    <div>
      <div className={styles.header}>
        <h1 className={styles.title}>Tableau de bord</h1>
        <span className={styles.subtitle}>{currentOrg.organization_name}</span>
      </div>

      <div className={styles.grid}>
        <KpiCard label="Appels (total)" value={calls.length} />
        <KpiCard label="Entrants" value={inbound} />
        <KpiCard label="Sortants" value={outbound} />
        <KpiCard label="Réussis" value={completed} />
        <KpiCard label="Transferts humains" value={transferred} />
        <KpiCard label="Agents actifs" value={agents.length} />
      </div>

      <div className={styles.section}>
        <div className={styles.sectionHeader}>Derniers appels</div>
        {loading ? (
          <div className={styles.emptyState}>Chargement…</div>
        ) : calls.length === 0 ? (
          <div className={styles.emptyState}>
            Aucun appel pour l'instant. Rendez-vous sur la page « Appels »
            pour en simuler un (mode Mock, sans coût).
          </div>
        ) : (
          calls.slice(0, 8).map((call) => (
            <div key={call.id} className={styles.callRow}>
              <span className={`${styles.badge} ${call.direction === "inbound" ? styles.badgeInbound : styles.badgeOutbound}`}>
                {call.direction === "inbound" ? "Entrant" : "Sortant"}
              </span>
              <span>{call.summary || "Sans résumé"}</span>
              <span style={{ color: "var(--color-muted)", fontFamily: "var(--font-mono)", fontSize: 12 }}>
                {call.provider}
              </span>
              <span style={{ display: "flex", alignItems: "center", gap: 6, color: "var(--color-signal)" }}>
                <Waveform />
                {call.status}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
