"use client";

import { useEffect, useState } from "react";
import { LifeBuoy, CircleDot, Flame, CheckCircle2 } from "lucide-react";
import { useOrganization } from "@/lib/OrganizationContext";
import { api, Ticket } from "@/lib/api";
import { KpiCard } from "@/components/KpiCard";
import { SkeletonRow } from "@/components/Skeleton";
import styles from "./tickets.module.css";

const PRIORITY_CLASS: Record<string, string> = {
  basse: styles.priorityBasse,
  normale: styles.priorityNormale,
  haute: styles.priorityHaute,
  urgente: styles.priorityUrgente,
};

const STATUS_FILTERS = ["Tous", "ouvert", "en_cours", "résolu", "fermé"];

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString("fr-FR", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

export default function TicketsPage() {
  const { currentOrg } = useOrganization();
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("Tous");

  const load = () => {
    if (!currentOrg) return;
    setLoading(true);
    api.listTickets(currentOrg.organization_id).then(setTickets).finally(() => setLoading(false));
  };

  useEffect(load, [currentOrg]);

  async function updateStatus(id: string, status: string) {
    if (!currentOrg) return;
    await api.updateTicket(currentOrg.organization_id, id, { status });
    load();
  }

  if (!currentOrg) {
    return <p style={{ color: "var(--color-muted)" }}>Sélectionnez ou créez une organisation.</p>;
  }

  const open = tickets.filter((t) => t.status === "ouvert").length;
  const urgent = tickets.filter((t) => (t.priority === "haute" || t.priority === "urgente") && t.status !== "résolu" && t.status !== "fermé").length;
  const resolved = tickets.filter((t) => t.status === "résolu").length;

  const filtered = filter === "Tous" ? tickets : tickets.filter((t) => t.status === filter);

  return (
    <div>
      <div className={styles.header}>
        <h1 className={styles.title}>Tickets</h1>
      </div>

      <div className={styles.grid}>
        <KpiCard label="Total" value={tickets.length} icon={LifeBuoy} accent="navy" />
        <KpiCard label="Ouverts" value={open} icon={CircleDot} accent="amber" />
        <KpiCard label="Priorité haute+" value={urgent} icon={Flame} accent="red" />
        <KpiCard label="Résolus" value={resolved} icon={CheckCircle2} accent="signal" />
      </div>

      <div className={styles.filterBar}>
        {STATUS_FILTERS.map((f) => (
          <button
            key={f}
            className={`${styles.filterButton} ${filter === f ? styles.filterButtonActive : ""}`}
            onClick={() => setFilter(f)}
          >
            {f === "Tous" ? "Tous" : f}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="surface-card"><SkeletonRow /><SkeletonRow /><SkeletonRow /></div>
      ) : filtered.length === 0 ? (
        <div className="surface-card">
          <div className={styles.emptyState}>
            <LifeBuoy size={26} strokeWidth={1.5} className={styles.emptyIcon} />
            <p>
              Aucun ticket pour l'instant. Ils apparaissent automatiquement quand un agent avec le
              "service client" activé reçoit un appel entrant.
            </p>
          </div>
        </div>
      ) : (
        filtered.map((t) => (
          <div key={t.id} className={styles.card}>
            <div className={styles.topRow}>
              <span className={styles.subject}>{t.subject}</span>
              {t.category && <span className={styles.category}>{t.category}</span>}
              <span className={`${styles.tag} ${PRIORITY_CLASS[t.priority] || styles.priorityNormale}`}>
                {t.priority}
              </span>
            </div>
            {t.description && <div className={styles.description}>{t.description}</div>}
            {t.resolution_notes && <div className={styles.resolutionNotes}>Résolution : {t.resolution_notes}</div>}
            <div className={styles.bottomRow}>
              <span className={styles.timestamp}>Créé le {formatDate(t.created_at)}</span>
              <select className={styles.statusSelect} value={t.status} onChange={(e) => updateStatus(t.id, e.target.value)}>
                <option value="ouvert">Ouvert</option>
                <option value="en_cours">En cours</option>
                <option value="résolu">Résolu</option>
                <option value="fermé">Fermé</option>
              </select>
            </div>
          </div>
        ))
      )}
    </div>
  );
}
