"use client";

import { useEffect, useState } from "react";
import { MessageCircle } from "lucide-react";
import { useOrganization } from "@/lib/OrganizationContext";
import { api, SmsLog } from "@/lib/api";
import { SkeletonRow } from "@/components/Skeleton";
import styles from "./sms.module.css";

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString("fr-FR", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

export default function SmsPage() {
  const { currentOrg } = useOrganization();
  const [logs, setLogs] = useState<SmsLog[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!currentOrg) return;
    setLoading(true);
    api.listSms(currentOrg.organization_id).then(setLogs).finally(() => setLoading(false));
  }, [currentOrg]);

  if (!currentOrg) {
    return <p style={{ color: "var(--color-muted)" }}>Sélectionnez ou créez une organisation.</p>;
  }

  return (
    <div>
      <div className={styles.header}>
        <h1 className={styles.title}>SMS</h1>
      </div>
      <p className={styles.hint}>
        Aucun SMS n'est réellement délivré en mode Mock (contrairement à l'email, il n'existe pas d'équivalent
        gratuit de Mailhog pour le SMS) — cette page prouve que l'envoi a bien été déclenché, avec le bon contenu.
      </p>

      {loading ? (
        <div className="surface-card"><SkeletonRow /><SkeletonRow /></div>
      ) : logs.length === 0 ? (
        <div className="surface-card">
          <div className={styles.emptyState}>
            <MessageCircle size={26} strokeWidth={1.5} className={styles.emptyIcon} />
            <p>Aucun SMS envoyé pour l'instant. Ils apparaissent ici après une réservation confirmée.</p>
          </div>
        </div>
      ) : (
        logs.map((log) => (
          <div key={log.id} className={styles.card}>
            <div className={styles.icon}><MessageCircle size={16} /></div>
            <div className={styles.details}>
              <div className={styles.toNumber}>{log.to_number}</div>
              <div className={styles.body}>{log.body}</div>
              <div className={styles.timestamp}>{formatDate(log.created_at)}</div>
            </div>
          </div>
        ))
      )}
    </div>
  );
}
