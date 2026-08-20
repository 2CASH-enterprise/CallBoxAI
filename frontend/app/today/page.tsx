"use client";

import { useEffect, useState } from "react";
import { Sunrise, LogIn, LogOut, MessageSquare, LifeBuoy } from "lucide-react";
import { useOrganization } from "@/lib/OrganizationContext";
import { api, TodayDashboard } from "@/lib/api";
import { Skeleton } from "@/components/Skeleton";
import styles from "./today.module.css";

const PRIORITY_COLOR: Record<string, string> = {
  basse: "var(--color-signal)",
  normale: "var(--color-muted)",
  haute: "var(--color-amber)",
  urgente: "var(--color-red)",
};

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
}

function formatDay(): string {
  return new Date().toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" });
}

export default function TodayPage() {
  const { currentOrg } = useOrganization();
  const [data, setData] = useState<TodayDashboard | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!currentOrg) return;
    setLoading(true);
    api.getTodayDashboard(currentOrg.organization_id).then(setData).finally(() => setLoading(false));
  }, [currentOrg]);

  if (!currentOrg) {
    return <p style={{ color: "var(--color-muted)" }}>Sélectionnez ou créez une organisation.</p>;
  }

  if (loading || !data) {
    return (
      <div>
        <Skeleton height={32} width={260} />
        <div style={{ marginTop: 24 }}><Skeleton height={80} radius={12} /></div>
      </div>
    );
  }

  return (
    <div>
      <div className={styles.header}>
        <h1 className={styles.title}>Aujourd'hui</h1>
        <p className={styles.subtitle}>{formatDay()}</p>
      </div>

      <div className={styles.summaryBanner}>
        <div className={styles.summaryIcon}><Sunrise size={20} /></div>
        <div className={styles.summaryText}>
          Cette nuit, l'agent a géré <strong>{data.overnight_summary.total_calls}</strong> appel(s), dont{" "}
          <strong>{data.overnight_summary.reservations_made}</strong> réservation(s).
        </div>
      </div>

      <div className={styles.grid}>
        <div className={styles.section}>
          <div className={styles.sectionHeader}>
            <LogIn size={13} /> Arrivées du jour
            <span className={styles.countBadge}>{data.arrivals_today.length}</span>
          </div>
          {data.arrivals_today.length === 0 ? (
            <div className={styles.emptyState}>Aucune arrivée prévue aujourd'hui.</div>
          ) : (
            data.arrivals_today.map((r) => (
              <div key={r.appointment_id} className={styles.row}>
                <div className={styles.rowTop}>
                  <span className={styles.rowName}>{r.contact_name}</span>
                  <span className={styles.rowMeta}>{formatTime(r.check_in)}</span>
                </div>
                <div className={styles.rowContent}>{r.room_type} · {r.contact_phone}</div>
              </div>
            ))
          )}
        </div>

        <div className={styles.section}>
          <div className={styles.sectionHeader}>
            <LogOut size={13} /> Départs du jour
            <span className={styles.countBadge}>{data.departures_today.length}</span>
          </div>
          {data.departures_today.length === 0 ? (
            <div className={styles.emptyState}>Aucun départ prévu aujourd'hui.</div>
          ) : (
            data.departures_today.map((r) => (
              <div key={r.appointment_id} className={styles.row}>
                <div className={styles.rowTop}>
                  <span className={styles.rowName}>{r.contact_name}</span>
                  <span className={styles.rowMeta}>{formatTime(r.check_out || r.check_in)}</span>
                </div>
                <div className={styles.rowContent}>{r.room_type} · {r.contact_phone}</div>
              </div>
            ))
          )}
        </div>

        <div className={styles.section}>
          <div className={styles.sectionHeader}>
            <MessageSquare size={13} /> Messages à traiter
            <span className={styles.countBadge}>{data.pending_messages.length}</span>
          </div>
          {data.pending_messages.length === 0 ? (
            <div className={styles.emptyState}>Aucun message en attente.</div>
          ) : (
            data.pending_messages.map((m) => (
              <div key={m.message_id} className={styles.row}>
                <div className={styles.rowTop}>
                  <span className={styles.rowName}>
                    {m.caller_name || "Appelant inconnu"}
                    {m.urgent && <span className={styles.urgentTag}>Urgent</span>}
                  </span>
                  <span className={styles.rowMeta}>{formatTime(m.created_at)}</span>
                </div>
                <div className={styles.rowContent}>{m.content}</div>
              </div>
            ))
          )}
        </div>

        <div className={styles.section}>
          <div className={styles.sectionHeader}>
            <LifeBuoy size={13} /> Tickets ouverts
            <span className={styles.countBadge}>{data.open_tickets.length}</span>
          </div>
          {data.open_tickets.length === 0 ? (
            <div className={styles.emptyState}>Aucun ticket ouvert.</div>
          ) : (
            data.open_tickets.map((t) => (
              <div key={t.ticket_id} className={styles.row}>
                <div className={styles.rowTop}>
                  <span className={styles.rowName}>{t.subject}</span>
                  <span className={styles.priorityTag} style={{ background: "var(--color-bg)", color: PRIORITY_COLOR[t.priority] }}>
                    {t.priority}
                  </span>
                </div>
                <div className={styles.rowContent}>{t.category}</div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
