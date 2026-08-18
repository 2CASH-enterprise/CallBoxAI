"use client";

import { useEffect, useState } from "react";
import { Download, TrendingDown } from "lucide-react";
import { useOrganization } from "@/lib/OrganizationContext";
import { api, Pipeline } from "@/lib/api";
import { Skeleton } from "@/components/Skeleton";
import styles from "./pipeline.module.css";

const STAGE_COLORS: Record<string, string> = {
  "Nouveau": "var(--color-violet)",
  "Contacté": "var(--color-muted)",
  "Intéressé": "var(--color-amber)",
  "RDV": "var(--color-signal)",
  "Converti": "var(--color-navy)",
};

const EXPORT_OPTIONS = [
  { value: "", label: "Tous les contacts" },
  { value: "Intéressé", label: "Leads qualifiés (Intéressé)" },
  { value: "RDV", label: "Rendez-vous pris" },
  { value: "Converti", label: "Convertis" },
];

export default function PipelinePage() {
  const { currentOrg } = useOrganization();
  const [pipeline, setPipeline] = useState<Pipeline | null>(null);
  const [loading, setLoading] = useState(true);
  const [exportStatus, setExportStatus] = useState("");
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    if (!currentOrg) return;
    setLoading(true);
    api.getPipeline(currentOrg.organization_id).then(setPipeline).finally(() => setLoading(false));
  }, [currentOrg]);

  async function handleExport() {
    if (!currentOrg) return;
    setExporting(true);
    try {
      await api.exportContacts(currentOrg.organization_id, exportStatus || undefined);
    } finally {
      setExporting(false);
    }
  }

  if (!currentOrg) {
    return <p style={{ color: "var(--color-muted)" }}>Sélectionnez ou créez une organisation.</p>;
  }

  if (loading || !pipeline) {
    return (
      <div>
        <Skeleton height={32} width={220} />
        <div style={{ marginTop: 24 }}>
          <Skeleton height={220} radius={12} />
        </div>
      </div>
    );
  }

  const maxCount = Math.max(...pipeline.funnel.map((s) => s.count), 1);

  return (
    <div>
      <div className={styles.header}>
        <h1 className={styles.title}>Pipeline de qualification</h1>
        <div className={styles.exportBar}>
          <select className={styles.exportSelect} value={exportStatus} onChange={(e) => setExportStatus(e.target.value)}>
            {EXPORT_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
          <button className="btn btn-primary" onClick={handleExport} disabled={exporting}>
            <Download size={14} /> {exporting ? "Export…" : "Exporter en CSV"}
          </button>
        </div>
      </div>

      <div className={styles.funnelSection}>
        <div className={styles.sectionHeader}>
          <TrendingDown size={13} style={{ verticalAlign: "-2px", marginRight: 6 }} />
          Entonnoir ({pipeline.total_contacts} contacts au total)
        </div>
        {pipeline.funnel.map((stage) => (
          <div key={stage.status} className={styles.funnelStage}>
            <span className={styles.funnelLabel}>{stage.status}</span>
            <div className={styles.funnelTrack}>
              <div
                className={styles.funnelFill}
                style={{
                  width: `${Math.max((stage.count / maxCount) * 100, stage.count > 0 ? 6 : 0)}%`,
                  background: STAGE_COLORS[stage.status] || "var(--color-navy)",
                }}
              />
            </div>
            <span className={styles.funnelCount}>{stage.count}</span>
          </div>
        ))}
      </div>

      <div className={styles.sideBuckets}>
        {pipeline.side_buckets.map((bucket) => (
          <div key={bucket.status} className={styles.sideBucketCard}>
            <div className={styles.sideBucketLabel}>{bucket.status}</div>
            <div className={styles.sideBucketCount}>{bucket.count}</div>
          </div>
        ))}
      </div>

      <p className={styles.note}>
        La qualification vient automatiquement de l'issue de chaque appel (Analytics). Exportez les leads
        qualifiés pour les transmettre à votre équipe commerciale.
      </p>
    </div>
  );
}
