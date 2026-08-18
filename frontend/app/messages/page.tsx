"use client";

import { useEffect, useState } from "react";
import { MessageSquare, PhoneMissed, AlertTriangle, Check, Eye } from "lucide-react";
import { useOrganization } from "@/lib/OrganizationContext";
import { api, Message } from "@/lib/api";
import { KpiCard } from "@/components/KpiCard";
import { SkeletonRow } from "@/components/Skeleton";
import styles from "./messages.module.css";

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString("fr-FR", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

export default function MessagesPage() {
  const { currentOrg } = useOrganization();
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);

  const load = () => {
    if (!currentOrg) return;
    setLoading(true);
    api.listMessages(currentOrg.organization_id).then(setMessages).finally(() => setLoading(false));
  };

  useEffect(load, [currentOrg]);

  async function updateStatus(id: string, status: string) {
    if (!currentOrg) return;
    await api.updateMessage(currentOrg.organization_id, id, status);
    load();
  }

  if (!currentOrg) {
    return <p style={{ color: "var(--color-muted)" }}>Sélectionnez ou créez une organisation.</p>;
  }

  const newCount = messages.filter((m) => m.status === "new").length;
  const urgentCount = messages.filter((m) => m.urgent && m.status !== "handled").length;

  return (
    <div>
      <div className={styles.header}>
        <h1 className={styles.title}>Messages</h1>
      </div>

      <div className={styles.grid}>
        <KpiCard label="Total" value={messages.length} icon={MessageSquare} accent="navy" />
        <KpiCard label="Non lus" value={newCount} icon={PhoneMissed} accent="violet" />
        <KpiCard label="Urgents" value={urgentCount} icon={AlertTriangle} accent="red" />
      </div>

      {loading ? (
        <div className="surface-card"><SkeletonRow /><SkeletonRow /><SkeletonRow /></div>
      ) : messages.length === 0 ? (
        <div className="surface-card">
          <div className={styles.emptyState}>
            <MessageSquare size={26} strokeWidth={1.5} className={styles.emptyIcon} />
            <p>
              Aucun message pour l'instant. Ils apparaissent automatiquement ici quand un appel entrant
              arrive en dehors des horaires d'ouverture d'un agent (télé-secrétariat).
            </p>
          </div>
        </div>
      ) : (
        messages.map((m) => (
          <div key={m.id} className={`${styles.card} ${m.urgent ? styles.cardUrgent : ""}`}>
            <div className={styles.icon}>
              <PhoneMissed size={16} />
            </div>
            <div className={styles.details}>
              <div className={styles.topRow}>
                <span className={styles.callerName}>{m.caller_name || "Appelant inconnu"}</span>
                <span className={styles.callerPhone}>{m.caller_phone}</span>
                {m.urgent && <span className={styles.urgentTag}>Urgent</span>}
              </div>
              <div className={styles.content}>{m.content}</div>
              <div className={styles.timestamp}>{formatDate(m.created_at)} · {m.status}</div>
            </div>
            <div className={styles.actions}>
              {m.status === "new" && (
                <button className="btn btn-ghost" onClick={() => updateStatus(m.id, "read")} title="Marquer comme lu">
                  <Eye size={13} />
                </button>
              )}
              {m.status !== "handled" && (
                <button className="btn btn-ghost" onClick={() => updateStatus(m.id, "handled")} title="Marquer comme traité">
                  <Check size={13} />
                </button>
              )}
            </div>
          </div>
        ))
      )}
    </div>
  );
}
