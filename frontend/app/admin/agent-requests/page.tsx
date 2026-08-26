"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/AuthContext";
import { api, AgentRequest } from "@/lib/api";
import { AGENT_TEMPLATES, AgentTemplateFields } from "@/lib/agentTemplates";
import { SkeletonRow } from "@/components/Skeleton";
import styles from "./agent-requests.module.css";

const STATUS_FILTERS = ["pending", "in_progress", "completed", "rejected", "Tous"];

const STATUS_COLORS: Record<string, { bg: string; color: string }> = {
  pending: { bg: "var(--color-amber-soft)", color: "var(--color-amber)" },
  in_progress: { bg: "var(--color-violet-soft)", color: "var(--color-violet)" },
  completed: { bg: "var(--color-signal-soft)", color: "var(--color-signal)" },
  rejected: { bg: "var(--color-red-soft)", color: "var(--color-red)" },
};

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("fr-FR", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

export default function AgentRequestsPage() {
  const { user } = useAuth();
  const router = useRouter();
  const [requests, setRequests] = useState<AgentRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("pending");

  const [fulfillTarget, setFulfillTarget] = useState<AgentRequest | null>(null);
  const [fulfillForm, setFulfillForm] = useState<AgentTemplateFields | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const [rejectTarget, setRejectTarget] = useState<AgentRequest | null>(null);
  const [rejectReason, setRejectReason] = useState("");

  useEffect(() => {
    if (user && !user.is_super_admin) {
      router.replace("/dashboard");
    }
  }, [user, router]);

  const load = () => {
    if (!user?.is_super_admin) return;
    setLoading(true);
    api.listAllAgentRequests(filter === "Tous" ? undefined : filter).then(setRequests).finally(() => setLoading(false));
  };

  useEffect(load, [user, filter]);

  function openFulfillForm(request: AgentRequest) {
    const template = AGENT_TEMPLATES.find((t) => t.key === request.use_case) || AGENT_TEMPLATES[AGENT_TEMPLATES.length - 1];
    setFulfillTarget(request);
    setFulfillForm({ ...template.fields });
  }

  async function handleFulfill(e: React.FormEvent) {
    e.preventDefault();
    if (!fulfillTarget || !fulfillForm) return;
    setSubmitting(true);
    try {
      await api.fulfillAgentRequest(fulfillTarget.id, fulfillForm);
      setFulfillTarget(null);
      setFulfillForm(null);
      load();
    } finally {
      setSubmitting(false);
    }
  }

  async function handleReject() {
    if (!rejectTarget) return;
    await api.updateAgentRequestStatus(rejectTarget.id, { status: "rejected", admin_notes: rejectReason.trim() || undefined });
    setRejectTarget(null);
    setRejectReason("");
    load();
  }

  async function markInProgress(request: AgentRequest) {
    await api.updateAgentRequestStatus(request.id, { status: "in_progress" });
    load();
  }

  if (!user?.is_super_admin) return null;

  return (
    <div>
      <div className={styles.header}>
        <h1 className={styles.title}>Demandes de création d'agent</h1>
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
        <div className="surface-card"><SkeletonRow /><SkeletonRow /></div>
      ) : requests.length === 0 ? (
        <p style={{ color: "var(--color-muted)" }}>Aucune demande pour ce filtre.</p>
      ) : (
        requests.map((r) => {
          const template = AGENT_TEMPLATES.find((t) => t.key === r.use_case);
          const statusStyle = STATUS_COLORS[r.status] || STATUS_COLORS.pending;
          return (
            <div key={r.id} className={styles.card}>
              <div className={styles.cardTop}>
                <div>
                  <div className={styles.orgName}>{r.organization_name}</div>
                  <div className={styles.useCase}>{template?.label || r.use_case} · {formatDate(r.created_at)}</div>
                </div>
                <span className={styles.statusTag} style={{ background: statusStyle.bg, color: statusStyle.color }}>
                  {r.status}
                </span>
              </div>
              <p className={styles.objective}>{r.objective}</p>
              {r.admin_notes && (
                <p style={{ fontSize: 12.5, color: "var(--color-muted)", marginBottom: 12 }}>Note : {r.admin_notes}</p>
              )}
              {(r.status === "pending" || r.status === "in_progress") && (
                <div className={styles.actions}>
                  {r.status === "pending" && (
                    <button className="btn btn-ghost" onClick={() => markInProgress(r)}>
                      Marquer en cours
                    </button>
                  )}
                  <button className="btn btn-primary" onClick={() => openFulfillForm(r)}>
                    Créer l'agent
                  </button>
                  <button className="btn btn-ghost" onClick={() => setRejectTarget(r)}>
                    Refuser
                  </button>
                </div>
              )}
            </div>
          );
        })
      )}

      {fulfillTarget && fulfillForm && (
        <div className={styles.formOverlay} onClick={() => { setFulfillTarget(null); setFulfillForm(null); }}>
          <form className={styles.formModal} onClick={(e) => e.stopPropagation()} onSubmit={handleFulfill}>
            <h2>Créer l'agent pour {fulfillTarget.organization_name}</h2>
            <p style={{ fontSize: 12.5, color: "var(--color-muted)", margin: 0 }}>
              Pré-rempli depuis le modèle "{AGENT_TEMPLATES.find((t) => t.key === fulfillTarget.use_case)?.label || fulfillTarget.use_case}"
              — ajustez selon la demande : <em>{fulfillTarget.objective}</em>
            </p>

            <div>
              <label>Nom de l'agent</label>
              <input required value={fulfillForm.name} onChange={(e) => setFulfillForm({ ...fulfillForm, name: e.target.value })} />
            </div>
            <div>
              <label>Objectif</label>
              <input value={fulfillForm.objective} onChange={(e) => setFulfillForm({ ...fulfillForm, objective: e.target.value })} />
            </div>
            <div>
              <label>Prompt système</label>
              <textarea rows={8} value={fulfillForm.system_prompt} onChange={(e) => setFulfillForm({ ...fulfillForm, system_prompt: e.target.value })} />
            </div>
            <div>
              <label>Langue</label>
              <select value={fulfillForm.language} onChange={(e) => setFulfillForm({ ...fulfillForm, language: e.target.value })}>
                <option value="fr">Français</option>
                <option value="en">Anglais</option>
                <option value="wo">Wolof</option>
                <option value="multi">Multilingue (détection automatique)</option>
              </select>
            </div>
            <div style={{ display: "flex", gap: 10 }}>
              <div style={{ flex: 1 }}>
                <label>Horaires début</label>
                <input type="time" value={fulfillForm.business_hours_start} onChange={(e) => setFulfillForm({ ...fulfillForm, business_hours_start: e.target.value })} />
              </div>
              <div style={{ flex: 1 }}>
                <label>Horaires fin</label>
                <input type="time" value={fulfillForm.business_hours_end} onChange={(e) => setFulfillForm({ ...fulfillForm, business_hours_end: e.target.value })} />
              </div>
            </div>
            <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
              <input type="checkbox" checked={fulfillForm.ticketing_enabled} onChange={(e) => setFulfillForm({ ...fulfillForm, ticketing_enabled: e.target.checked })} />
              Service client (tickets)
            </label>
            <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
              <input type="checkbox" checked={fulfillForm.pms_enabled} onChange={(e) => setFulfillForm({ ...fulfillForm, pms_enabled: e.target.checked })} />
              PMS (réservations en direct)
            </label>
            <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
              <input type="checkbox" checked={fulfillForm.kyc_enabled} onChange={(e) => setFulfillForm({ ...fulfillForm, kyc_enabled: e.target.checked })} />
              KYC (lien envoyé par SMS)
            </label>
            {fulfillForm.kyc_enabled && (
              <div>
                <label>Lien KYC du partenaire</label>
                <input value={fulfillForm.kyc_link_url} onChange={(e) => setFulfillForm({ ...fulfillForm, kyc_link_url: e.target.value })} />
              </div>
            )}
            <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
              <input type="checkbox" checked={fulfillForm.transfer_enabled} onChange={(e) => setFulfillForm({ ...fulfillForm, transfer_enabled: e.target.checked })} />
              Transfert humain
            </label>
            {fulfillForm.transfer_enabled && (
              <div>
                <label>Numéro de transfert</label>
                <input value={fulfillForm.transfer_number} onChange={(e) => setFulfillForm({ ...fulfillForm, transfer_number: e.target.value })} />
              </div>
            )}

            <div className={styles.formActions}>
              <button type="button" className="btn btn-ghost" onClick={() => { setFulfillTarget(null); setFulfillForm(null); }}>
                Annuler
              </button>
              <button type="submit" className="btn btn-primary" disabled={submitting}>
                {submitting ? "Création…" : "Créer l'agent"}
              </button>
            </div>
          </form>
        </div>
      )}

      {rejectTarget && (
        <div className={styles.formOverlay} onClick={() => setRejectTarget(null)}>
          <div className={styles.formModal} onClick={(e) => e.stopPropagation()} style={{ width: 420 }}>
            <h2>Refuser la demande</h2>
            <div>
              <label>Motif (visible par le client)</label>
              <textarea rows={3} value={rejectReason} onChange={(e) => setRejectReason(e.target.value)} placeholder="Ex. Merci de préciser le secteur d'activité" />
            </div>
            <div className={styles.formActions}>
              <button className="btn btn-ghost" onClick={() => setRejectTarget(null)}>Annuler</button>
              <button className="btn btn-signal" onClick={handleReject}>Confirmer le refus</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
