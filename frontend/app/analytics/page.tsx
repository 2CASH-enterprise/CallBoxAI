"use client";

import { useEffect, useState } from "react";
import { useOrganization } from "@/lib/OrganizationContext";
import { api, AnalyticsSummary, AnalyticsBreakdownItem } from "@/lib/api";
import { KpiCard } from "@/components/KpiCard";
import styles from "./analytics.module.css";

function Breakdown({ title, items }: { title: string; items: AnalyticsBreakdownItem[] }) {
  const max = Math.max(...items.map((i) => i.count), 1);
  return (
    <div className={styles.section}>
      <div className={styles.sectionHeader}>{title}</div>
      {items.length === 0 ? (
        <div className={styles.emptyState}>Aucune donnée pour l'instant.</div>
      ) : (
        items.map((item) => (
          <div key={item.label} className={styles.barRow}>
            <span className={styles.barLabel}>{item.label}</span>
            <div className={styles.barTrack}>
              <div className={styles.barFill} style={{ width: `${(item.count / max) * 100}%` }} />
            </div>
            <span className={styles.barCount}>{item.count}</span>
          </div>
        ))
      )}
    </div>
  );
}

export default function AnalyticsPage() {
  const { currentOrg } = useOrganization();
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!currentOrg) return;
    setLoading(true);
    api.getAnalyticsSummary(currentOrg.organization_id).then(setSummary).finally(() => setLoading(false));
  }, [currentOrg]);

  if (!currentOrg) {
    return <p style={{ color: "var(--color-muted)" }}>Sélectionnez ou créez une organisation.</p>;
  }

  if (loading || !summary) {
    return <p style={{ color: "var(--color-muted)" }}>Chargement…</p>;
  }

  return (
    <div>
      <div className={styles.header}>
        <h1 className={styles.title}>Analytics</h1>
      </div>

      <div className={styles.grid}>
        <KpiCard label="Appels analysés" value={summary.total_calls} />
        <KpiCard label="Score moyen" value={summary.avg_score ?? "—"} />
        <KpiCard label="Taux de qualification" value={`${summary.qualification_rate}%`} />
        <KpiCard label="Taux de rendez-vous" value={`${summary.appointment_rate}%`} />
        <KpiCard label="Taux de transfert" value={`${summary.transfer_rate}%`} />
      </div>

      <div className={styles.splitGrid}>
        <Breakdown title="Motifs d'appel (intent)" items={summary.by_intent} />
        <Breakdown title="Qualification" items={summary.by_qualification} />
      </div>

      <Breakdown title="Sentiment" items={summary.by_sentiment} />

      <div className={styles.section}>
        <div className={styles.sectionHeader}>Performance par agent</div>
        {summary.by_agent.length === 0 ? (
          <div className={styles.emptyState}>Aucun agent avec des appels pour l'instant.</div>
        ) : (
          <>
            <div className={`${styles.row} ${styles.rowHead}`}>
              <span>Agent</span>
              <span>Appels</span>
              <span>Score moyen</span>
            </div>
            {summary.by_agent.map((a) => (
              <div key={a.agent_id} className={styles.row}>
                <span>{a.agent_name}</span>
                <span>{a.calls_count}</span>
                <span>{a.avg_score ?? "—"}</span>
              </div>
            ))}
          </>
        )}
      </div>
    </div>
  );
}
