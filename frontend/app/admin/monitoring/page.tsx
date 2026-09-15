"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { CheckCircle2 } from "lucide-react";
import { useAuth } from "@/lib/AuthContext";
import { api, ErrorLogEntry } from "@/lib/api";
import { SkeletonRow } from "@/components/Skeleton";
import styles from "./monitoring.module.css";

type Filter = "unresolved" | "resolved" | "all";

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

export default function MonitoringPage() {
  const { user } = useAuth();
  const router = useRouter();
  const [errors, setErrors] = useState<ErrorLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<Filter>("unresolved");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => {
    if (user && !user.is_super_admin) {
      router.replace("/dashboard");
    }
  }, [user, router]);

  function load() {
    setLoading(true);
    const resolvedParam = filter === "all" ? undefined : filter === "resolved";
    api.listErrorLogs(resolvedParam).then(setErrors).finally(() => setLoading(false));
  }

  useEffect(() => {
    if (!user?.is_super_admin) return;
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, filter]);

  async function handleResolve(id: string) {
    await api.resolveErrorLog(id);
    load();
  }

  if (!user?.is_super_admin) return null;

  return (
    <div>
      <div className={styles.header}>
        <h1 className={styles.title}>Monitoring des erreurs</h1>
      </div>
      <p className={styles.subtitle}>
        Défaillances techniques capturées automatiquement (provisionnement d&apos;agent, outils PMS, webhooks...) —
        jamais visible par vos clients, pour piloter la plateforme sans dépendre des journaux serveur.
      </p>

      <div className={styles.filterBar}>
        <button
          className={`${styles.filterButton} ${filter === "unresolved" ? styles.filterButtonActive : ""}`}
          onClick={() => setFilter("unresolved")}
        >
          Non résolues
        </button>
        <button
          className={`${styles.filterButton} ${filter === "resolved" ? styles.filterButtonActive : ""}`}
          onClick={() => setFilter("resolved")}
        >
          Résolues
        </button>
        <button
          className={`${styles.filterButton} ${filter === "all" ? styles.filterButtonActive : ""}`}
          onClick={() => setFilter("all")}
        >
          Toutes
        </button>
      </div>

      {loading ? (
        <div className="surface-card"><SkeletonRow columns={4} /><SkeletonRow columns={4} /><SkeletonRow columns={4} /></div>
      ) : (
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Date</th>
              <th>Source</th>
              <th>Message</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {errors.length === 0 ? (
              <tr>
                <td colSpan={4}>
                  <div className={styles.emptyState}>
                    <CheckCircle2 size={22} strokeWidth={1.5} style={{ marginBottom: 8 }} />
                    <p>{filter === "unresolved" ? "Aucune erreur non résolue — tout va bien." : "Aucune erreur trouvée."}</p>
                  </div>
                </td>
              </tr>
            ) : (
              errors.map((e) => (
                <tr key={e.id} className={!e.resolved ? styles.warningRow : ""}>
                  <td className={styles.orgName}>{formatDate(e.created_at)}</td>
                  <td><span className={styles.categoryTag}>{e.source}</span></td>
                  <td className={styles.messageCell}>
                    <div>{e.message}</div>
                    {e.details && (
                      <>
                        <button
                          className={styles.detailsToggle}
                          onClick={() => setExpandedId(expandedId === e.id ? null : e.id)}
                        >
                          {expandedId === e.id ? "Masquer le détail" : "Voir le détail"}
                        </button>
                        {expandedId === e.id && <pre className={styles.detailsPre}>{e.details}</pre>}
                      </>
                    )}
                  </td>
                  <td>
                    {!e.resolved && (
                      <button className={styles.resolveButton} onClick={() => handleResolve(e.id)}>
                        Marquer résolue
                      </button>
                    )}
                    {e.resolved && (
                      <span className={styles.warningBadge} style={{ color: "var(--color-signal)" }}>
                        <CheckCircle2 size={12} /> Résolue
                      </span>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      )}
    </div>
  );
}
