"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AlertTriangle } from "lucide-react";
import { useAuth } from "@/lib/AuthContext";
import { api, AgentMargin } from "@/lib/api";
import { SkeletonRow } from "@/components/Skeleton";
import styles from "./margin.module.css";

// Seuil d'alerte (section 40) : coût réel par lead/RDV produit au-delà
// duquel une campagne mérite d'être regardée de plus près — purement
// indicatif, à ajuster selon vos tarifs réels. N'affecte jamais le client,
// jamais bloquant, juste un signal visuel pour vous.
const COST_PER_RESULT_WARNING_THRESHOLD_FCFA = 3000;

const CATEGORY_LABELS: Record<string, string> = {
  prospection: "Commercial — Acquisition",
  fidelisation: "Commercial — Fidélisation",
  hotellerie: "Réceptionniste",
  service_client: "Service Client",
  telesecretariat: "Télésecrétariat",
  telecom: "Télécom",
  generique: "Générique",
};

function formatFcfa(value: number): string {
  return `${value.toLocaleString("fr-FR")} FCFA`;
}

export default function MarginReportPage() {
  const { user } = useAuth();
  const router = useRouter();
  const [report, setReport] = useState<AgentMargin[]>([]);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(30);

  useEffect(() => {
    if (user && !user.is_super_admin) {
      router.replace("/dashboard");
    }
  }, [user, router]);

  useEffect(() => {
    if (!user?.is_super_admin) return;
    setLoading(true);
    api.getMarginReport(days).then(setReport).finally(() => setLoading(false));
  }, [user, days]);

  if (!user?.is_super_admin) return null;

  const totalCost = report.reduce((sum, r) => sum + r.real_cost_fcfa, 0);
  const totalMinutes = report.reduce((sum, r) => sum + r.total_minutes, 0);

  return (
    <div>
      <div className={styles.header}>
        <h1 className={styles.title}>Suivi interne de marge</h1>
      </div>
      <p className={styles.subtitle}>
        Coût réel (minutes payées à Retell/Twilio) face aux résultats produits, par agent — réservé à votre usage
        interne, jamais visible ni facturé au client de cette façon (le client paie un forfait "employé IA" à
        capacité). Les campagnes commerciales signalées dépassent {formatFcfa(COST_PER_RESULT_WARNING_THRESHOLD_FCFA)} par lead produit.
      </p>

      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        {[7, 30, 90].map((d) => (
          <button
            key={d}
            onClick={() => setDays(d)}
            style={{
              padding: "6px 14px", borderRadius: 20, fontSize: 12.5, border: "1px solid var(--color-line)",
              background: days === d ? "var(--color-navy)" : "var(--color-surface)",
              color: days === d ? "white" : "var(--color-muted)",
            }}
          >
            {d} jours
          </button>
        ))}
      </div>

      {!loading && report.length > 0 && (
        <p style={{ fontSize: 12.5, color: "var(--color-muted)", marginBottom: 12 }}>
          Total : {formatFcfa(totalCost)} pour {totalMinutes} minutes, tous agents confondus.
        </p>
      )}

      {loading ? (
        <div className="surface-card"><SkeletonRow /><SkeletonRow /></div>
      ) : report.length === 0 ? (
        <p style={{ color: "var(--color-muted)" }}>Aucune activité sur cette période.</p>
      ) : (
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Organisation / Agent</th>
              <th>Catégorie</th>
              <th>Appels</th>
              <th>Minutes</th>
              <th>Coût réel</th>
              <th>Résultats</th>
              <th>Coût / résultat</th>
            </tr>
          </thead>
          <tbody>
            {report.map((r) => {
              const isWarning = r.cost_per_result_fcfa !== null && r.cost_per_result_fcfa > COST_PER_RESULT_WARNING_THRESHOLD_FCFA;
              return (
                <tr key={r.agent_id} className={isWarning ? styles.warningRow : undefined}>
                  <td>
                    <div className={styles.agentName}>{r.agent_name}</div>
                    <div className={styles.orgName}>{r.organization_name}</div>
                  </td>
                  <td><span className={styles.categoryTag}>{CATEGORY_LABELS[r.category] || r.category}</span></td>
                  <td>{r.total_calls}</td>
                  <td>{r.total_minutes}</td>
                  <td className={styles.costCell}>{formatFcfa(r.real_cost_fcfa)}</td>
                  <td>{r.is_commercial ? r.results_count ?? 0 : "—"}</td>
                  <td className={styles.costCell}>
                    {r.cost_per_result_fcfa !== null ? (
                      <span className={isWarning ? styles.warningBadge : undefined}>
                        {isWarning && <AlertTriangle size={11} />}
                        {formatFcfa(r.cost_per_result_fcfa)}
                      </span>
                    ) : (
                      "—"
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}
