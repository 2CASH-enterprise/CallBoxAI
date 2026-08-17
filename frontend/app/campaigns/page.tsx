"use client";

import { useEffect, useRef, useState } from "react";
import { useOrganization } from "@/lib/OrganizationContext";
import { api, Agent, Campaign, CampaignDetail, BatchResult } from "@/lib/api";
import { KpiCard } from "@/components/KpiCard";
import styles from "./campaigns.module.css";

export default function CampaignsPage() {
  const { currentOrg } = useOrganization();
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<CampaignDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  const [modalOpen, setModalOpen] = useState(false);
  const [form, setForm] = useState({ name: "", agent_id: "", schedule_start: "08:00", schedule_end: "19:00", max_attempts: "3" });
  const [submitting, setSubmitting] = useState(false);

  const [importing, setImporting] = useState(false);
  const [importSummary, setImportSummary] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [runningBatch, setRunningBatch] = useState(false);
  const [lastBatch, setLastBatch] = useState<BatchResult | null>(null);

  const loadCampaigns = () => {
    if (!currentOrg) return;
    api.listCampaigns(currentOrg.organization_id).then((list) => {
      setCampaigns(list);
      if (!selectedId && list.length > 0) setSelectedId(list[0].id);
    });
    api.listAgents(currentOrg.organization_id).then((list) => {
      setAgents(list);
      if (list.length > 0) setForm((f) => ({ ...f, agent_id: f.agent_id || list[0].id }));
    });
  };

  useEffect(loadCampaigns, [currentOrg]);

  const loadDetail = () => {
    if (!currentOrg || !selectedId) return;
    setLoadingDetail(true);
    api.getCampaign(currentOrg.organization_id, selectedId).then(setDetail).finally(() => setLoadingDetail(false));
  };

  useEffect(() => {
    loadDetail();
    setImportSummary(null);
    setLastBatch(null);
  }, [selectedId, currentOrg]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!currentOrg || !form.name.trim() || !form.agent_id) return;
    setSubmitting(true);
    try {
      const created = await api.createCampaign(currentOrg.organization_id, {
        name: form.name.trim(),
        agent_id: form.agent_id,
        schedule_start: form.schedule_start,
        schedule_end: form.schedule_end,
        max_attempts: parseInt(form.max_attempts, 10) || 3,
      });
      setForm({ name: "", agent_id: agents[0]?.id || "", schedule_start: "08:00", schedule_end: "19:00", max_attempts: "3" });
      setModalOpen(false);
      setCampaigns((prev) => [...prev, created]);
      setSelectedId(created.id);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleImport(e: React.ChangeEvent<HTMLInputElement>) {
    if (!currentOrg || !selectedId || !e.target.files?.[0]) return;
    setImporting(true);
    setImportSummary(null);
    try {
      const summary = await api.importCampaignContacts(currentOrg.organization_id, selectedId, e.target.files[0]);
      setImportSummary(
        `${summary.imported} contact(s) importé(s), ${summary.skipped_invalid_phone} numéro(s) invalide(s) ignoré(s). Total dans la campagne : ${summary.total_targets}.`
      );
      loadDetail();
    } finally {
      setImporting(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function handleStart() {
    if (!currentOrg || !selectedId) return;
    await api.startCampaign(currentOrg.organization_id, selectedId);
    loadDetail();
  }

  async function handlePause() {
    if (!currentOrg || !selectedId) return;
    await api.pauseCampaign(currentOrg.organization_id, selectedId);
    loadDetail();
  }

  async function handleRunBatch() {
    if (!currentOrg || !selectedId) return;
    setRunningBatch(true);
    try {
      const result = await api.runCampaignBatch(currentOrg.organization_id, selectedId);
      setLastBatch(result);
      loadDetail();
    } finally {
      setRunningBatch(false);
    }
  }

  if (!currentOrg) {
    return <p style={{ color: "var(--color-muted)" }}>Sélectionnez ou créez une organisation.</p>;
  }

  return (
    <div>
      <div className={styles.header}>
        <h1 className={styles.title}>Campagnes</h1>
        <button className={styles.button} onClick={() => setModalOpen(true)}>
          + Nouvelle campagne
        </button>
      </div>

      <div className={styles.layout}>
        <div className={styles.panel}>
          <div className={styles.panelHeader}>Vos campagnes</div>
          {campaigns.length === 0 ? (
            <div className={styles.emptyState}>Aucune campagne pour l'instant.</div>
          ) : (
            campaigns.map((c) => (
              <button
                key={c.id}
                className={`${styles.campItem} ${selectedId === c.id ? styles.campItemActive : ""}`}
                onClick={() => setSelectedId(c.id)}
              >
                {c.name}
                <span className={styles.statusTag}>{c.status}</span>
              </button>
            ))
          )}
        </div>

        <div>
          {!selectedId ? (
            <p style={{ color: "var(--color-muted)" }}>Créez ou sélectionnez une campagne.</p>
          ) : loadingDetail && !detail ? (
            <p style={{ color: "var(--color-muted)" }}>Chargement…</p>
          ) : (
            detail && (
              <>
                <div className={styles.grid}>
                  <KpiCard label="Contacts" value={detail.stats.total} />
                  <KpiCard label="En attente" value={detail.stats.pending} />
                  <KpiCard label="Réussis" value={detail.stats.completed} />
                  <KpiCard label="Sans réponse" value={detail.stats.no_answer} />
                  <KpiCard label="Échecs" value={detail.stats.failed} />
                </div>

                <div className={styles.section}>
                  <div className={styles.sectionHeader}>Importer des contacts (CSV)</div>
                  <p style={{ fontSize: 13, color: "var(--color-muted)", marginBottom: 10 }}>
                    Colonnes attendues : <code>phone</code> (obligatoire), <code>first_name</code>, <code>last_name</code> (optionnelles).
                  </p>
                  <input ref={fileInputRef} type="file" accept=".csv" onChange={handleImport} disabled={importing} />
                  {importSummary && <p className={styles.batchResult}>{importSummary}</p>}
                </div>

                <div className={styles.section}>
                  <div className={styles.sectionHeader}>Pilotage</div>
                  <div className={styles.actionsBar}>
                    {detail.status !== "running" ? (
                      <button className={styles.primaryAction} onClick={handleStart} disabled={detail.status === "completed"}>
                        Démarrer la campagne
                      </button>
                    ) : (
                      <button onClick={handlePause}>Mettre en pause</button>
                    )}
                    <button onClick={handleRunBatch} disabled={runningBatch || detail.status !== "running"}>
                      {runningBatch ? "Traitement…" : "Lancer un lot d'appels"}
                    </button>
                    <span className={styles.scheduleNote}>
                      Horaires : {detail.schedule_start} - {detail.schedule_end} · {detail.max_attempts} tentative(s) max
                    </span>
                  </div>
                  {lastBatch && (
                    <p className={styles.batchResult}>
                      {lastBatch.message
                        ? lastBatch.message
                        : `Lot traité : ${lastBatch.processed} contact(s) — ${lastBatch.completed} réussi(s), ${lastBatch.no_answer} sans réponse (retentés), ${lastBatch.failed} échec(s) définitif(s).`}
                    </p>
                  )}
                </div>
              </>
            )
          )}
        </div>
      </div>

      {modalOpen && (
        <div className={styles.modalOverlay} onClick={() => setModalOpen(false)}>
          <form className={styles.modal} onClick={(e) => e.stopPropagation()} onSubmit={handleCreate}>
            <h2>Nouvelle campagne</h2>
            <div className={styles.form}>
              <input
                placeholder="Nom de la campagne"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                required
              />
              <select value={form.agent_id} onChange={(e) => setForm({ ...form, agent_id: e.target.value })} required>
                {agents.length === 0 && <option value="">Créez d'abord un agent</option>}
                {agents.map((a) => (
                  <option key={a.id} value={a.id}>{a.name}</option>
                ))}
              </select>
              <div className={styles.formRow}>
                <input
                  type="time"
                  value={form.schedule_start}
                  onChange={(e) => setForm({ ...form, schedule_start: e.target.value })}
                />
                <input
                  type="time"
                  value={form.schedule_end}
                  onChange={(e) => setForm({ ...form, schedule_end: e.target.value })}
                />
              </div>
              <input
                type="number"
                min={1}
                placeholder="Tentatives max par contact"
                value={form.max_attempts}
                onChange={(e) => setForm({ ...form, max_attempts: e.target.value })}
              />
            </div>
            <div className={styles.modalActions}>
              <button type="button" className={styles.cancelButton} onClick={() => setModalOpen(false)}>
                Annuler
              </button>
              <button type="submit" className={styles.button} disabled={submitting || agents.length === 0}>
                {submitting ? "Création…" : "Créer la campagne"}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
