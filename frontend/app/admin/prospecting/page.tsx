"use client";

import { useEffect, useState, Fragment } from "react";
import { useRouter } from "next/navigation";
import { Plus, Upload, Sparkles, ArrowLeft } from "lucide-react";
import { useAuth } from "@/lib/AuthContext";
import { api, ProspectingCampaign, ProspectingTarget } from "@/lib/api";
import { AGENT_TEMPLATES } from "@/lib/agentTemplates";
import { SkeletonRow } from "@/components/Skeleton";
import styles from "./prospecting.module.css";

const STATUS_LABELS: Record<string, string> = {
  imported: "Importée",
  analyzed: "Analysée",
  agent_created: "Agent créé",
  email_prepared: "Email préparé",
  sent: "Envoyé",
  opened: "Ouvert",
  clicked: "Cliqué",
  page_visited: "Page visitée",
  called: "Appelé",
  converted: "Converti",
};

export default function ProspectingPage() {
  const { user } = useAuth();
  const router = useRouter();

  const [campaigns, setCampaigns] = useState<ProspectingCampaign[]>([]);
  const [loadingCampaigns, setLoadingCampaigns] = useState(true);
  const [selectedCampaign, setSelectedCampaign] = useState<ProspectingCampaign | null>(null);
  const [targets, setTargets] = useState<ProspectingTarget[]>([]);
  const [loadingTargets, setLoadingTargets] = useState(false);

  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newName, setNewName] = useState("");
  const [newSector, setNewSector] = useState("");
  const [newAgentTemplate, setNewAgentTemplate] = useState(AGENT_TEMPLATES[0]?.key || "");
  const [creating, setCreating] = useState(false);

  const [importing, setImporting] = useState(false);
  const [importSummary, setImportSummary] = useState<string | null>(null);
  const [analyzingAll, setAnalyzingAll] = useState(false);
  const [analyzingTargetId, setAnalyzingTargetId] = useState<string | null>(null);
  const [expandedTargetId, setExpandedTargetId] = useState<string | null>(null);

  useEffect(() => {
    if (user && !user.is_super_admin) router.replace("/dashboard");
  }, [user, router]);

  function loadCampaigns() {
    setLoadingCampaigns(true);
    api.listProspectingCampaigns().then(setCampaigns).finally(() => setLoadingCampaigns(false));
  }

  useEffect(() => {
    if (user?.is_super_admin) loadCampaigns();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  function openCampaign(campaign: ProspectingCampaign) {
    setSelectedCampaign(campaign);
    setImportSummary(null);
    setLoadingTargets(true);
    api.listProspectingTargets(campaign.id).then(setTargets).finally(() => setLoadingTargets(false));
  }

  function refreshTargets() {
    if (!selectedCampaign) return;
    api.listProspectingTargets(selectedCampaign.id).then(setTargets);
  }

  async function handleCreateCampaign(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    try {
      await api.createProspectingCampaign({ name: newName.trim(), sector: newSector.trim(), agent_template_key: newAgentTemplate });
      setNewName("");
      setNewSector("");
      setShowCreateForm(false);
      loadCampaigns();
    } finally {
      setCreating(false);
    }
  }

  async function handleImport(e: React.ChangeEvent<HTMLInputElement>) {
    if (!selectedCampaign || !e.target.files?.[0]) return;
    setImporting(true);
    setImportSummary(null);
    try {
      const summary = await api.importProspectingTargets(selectedCampaign.id, e.target.files[0]);
      setImportSummary(
        `${summary.imported} cible(s) importée(s), ${summary.skipped} ligne(s) ignorée(s) (sans nom ou plafond de 50 atteint). Total dans la campagne : ${summary.total_in_campaign}.`
      );
      refreshTargets();
      loadCampaigns();
    } finally {
      setImporting(false);
      e.target.value = "";
    }
  }

  async function handleAnalyzeOne(targetId: string) {
    setAnalyzingTargetId(targetId);
    try {
      await api.analyzeProspectingTarget(selectedCampaign!.id, targetId);
      refreshTargets();
    } finally {
      setAnalyzingTargetId(null);
    }
  }

  async function handleAnalyzeAll() {
    if (!selectedCampaign) return;
    setAnalyzingAll(true);
    try {
      const result = await api.analyzeAllProspectingTargets(selectedCampaign.id);
      setImportSummary(`Analyse terminée : ${result.analyzed} réussie(s), ${result.failed} échec(s).`);
      refreshTargets();
    } finally {
      setAnalyzingAll(false);
    }
  }

  async function handleSaveEdit(target: ProspectingTarget, extractedInfo: string) {
    await api.updateProspectingTarget(selectedCampaign!.id, target.id, { extracted_info: extractedInfo });
    refreshTargets();
  }

  if (!user?.is_super_admin) return null;

  // ---------- Vue détail d'une campagne ----------
  if (selectedCampaign) {
    return (
      <div>
        <button className={styles.backLink} onClick={() => setSelectedCampaign(null)}>
          <ArrowLeft size={14} /> Retour aux campagnes
        </button>
        <div className={styles.header}>
          <h1 className={styles.title}>{selectedCampaign.name}</h1>
          <span className={styles.sectorTag}>{selectedCampaign.sector}</span>
        </div>
        <p className={styles.subtitle}>
          Modèle d&apos;agent démontré : <strong>{AGENT_TEMPLATES.find((t) => t.key === selectedCampaign.agent_template_key)?.label || selectedCampaign.agent_template_key}</strong>
        </p>

        <div className={styles.actionsBar}>
          <label className="btn btn-ghost" style={{ cursor: "pointer" }}>
            <Upload size={14} /> {importing ? "Import…" : "Importer un lot (CSV, 50 max)"}
            <input type="file" accept=".csv" onChange={handleImport} disabled={importing} style={{ display: "none" }} />
          </label>
          <button className="btn btn-primary" onClick={handleAnalyzeAll} disabled={analyzingAll || targets.length === 0}>
            <Sparkles size={14} /> {analyzingAll ? "Analyse en cours…" : "Analyser toutes les cibles importées"}
          </button>
        </div>
        {importSummary && <p className={styles.summaryNote}>{importSummary}</p>}
        <p className={styles.hint}>
          Colonnes attendues : <code>nom</code> (obligatoire), <code>adresse</code>, <code>telephone</code>, <code>site_internet</code>,{" "}
          <code>email</code>, <code>contact_name</code> — reconnaît aussi directement les en-têtes de l&apos;export Atout France.
        </p>

        <table className={styles.table}>
          <thead>
            <tr>
              <th>Établissement</th>
              <th>Site web</th>
              <th>Statut</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {loadingTargets ? (
              <>
                <SkeletonRow columns={4} /><SkeletonRow columns={4} />
              </>
            ) : targets.length === 0 ? (
              <tr><td colSpan={4} className={styles.emptyState}>Aucune cible importée pour l&apos;instant.</td></tr>
            ) : (
              targets.map((t) => (
                <Fragment key={t.id}>
                  <tr>
                    <td>
                      <div>{t.company_name}</div>
                      {t.address && <div className={styles.muted}>{t.address}</div>}
                    </td>
                    <td className={styles.muted}>{t.website_url || "—"}</td>
                    <td><span className={styles.statusTag}>{STATUS_LABELS[t.status] || t.status}</span></td>
                    <td style={{ display: "flex", gap: 8 }}>
                      <button
                        className={styles.smallAction}
                        onClick={() => handleAnalyzeOne(t.id)}
                        disabled={analyzingTargetId === t.id || !t.website_url}
                        title={!t.website_url ? "Aucun site web renseigné" : "Analyser (ou relancer l'analyse)"}
                      >
                        {analyzingTargetId === t.id ? "…" : "Analyser"}
                      </button>
                      {t.extracted_info && (
                        <button className={styles.smallAction} onClick={() => setExpandedTargetId(expandedTargetId === t.id ? null : t.id)}>
                          {expandedTargetId === t.id ? "Fermer" : "Voir la fiche"}
                        </button>
                      )}
                    </td>
                  </tr>
                  {expandedTargetId === t.id && (
                    <tr>
                      <td colSpan={4}>
                        <TargetVerification target={t} onSave={(text) => handleSaveEdit(t, text)} />
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))
            )}
          </tbody>
        </table>
      </div>
    );
  }

  // ---------- Vue liste des campagnes ----------
  return (
    <div>
      <div className={styles.header}>
        <h1 className={styles.title}>Prospection (outil interne)</h1>
        <button className="btn btn-primary" onClick={() => setShowCreateForm(!showCreateForm)}>
          <Plus size={14} /> Nouvelle campagne
        </button>
      </div>
      <p className={styles.subtitle}>
        Réservé à votre usage — jamais visible des clients. Un lot de cibles par campagne (50 maximum), un secteur, un modèle
        d&apos;agent à démontrer.
      </p>

      {showCreateForm && (
        <form className={styles.createForm} onSubmit={handleCreateCampaign}>
          <input placeholder="Nom de la campagne (ex. Hôtels lot 1)" required value={newName} onChange={(e) => setNewName(e.target.value)} />
          <input placeholder="Secteur (ex. hôtellerie)" required value={newSector} onChange={(e) => setNewSector(e.target.value)} />
          <select value={newAgentTemplate} onChange={(e) => setNewAgentTemplate(e.target.value)}>
            {AGENT_TEMPLATES.map((t) => (
              <option key={t.key} value={t.key}>{t.label}</option>
            ))}
          </select>
          <button type="submit" className="btn btn-primary" disabled={creating}>
            {creating ? "Création…" : "Créer"}
          </button>
        </form>
      )}

      <table className={styles.table}>
        <thead>
          <tr>
            <th>Campagne</th>
            <th>Secteur</th>
            <th>Cibles</th>
            <th>Créée le</th>
          </tr>
        </thead>
        <tbody>
          {loadingCampaigns ? (
            <><SkeletonRow columns={4} /><SkeletonRow columns={4} /></>
          ) : campaigns.length === 0 ? (
            <tr><td colSpan={4} className={styles.emptyState}>Aucune campagne pour l&apos;instant.</td></tr>
          ) : (
            campaigns.map((c) => (
              <tr key={c.id} className={styles.clickableRow} onClick={() => openCampaign(c)}>
                <td>{c.name}</td>
                <td><span className={styles.sectorTag}>{c.sector}</span></td>
                <td>{c.targets_count}</td>
                <td className={styles.muted}>{new Date(c.created_at).toLocaleDateString("fr-FR")}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

function TargetVerification({ target, onSave }: { target: ProspectingTarget; onSave: (text: string) => void }) {
  const [text, setText] = useState(target.extracted_info || "");
  const [saving, setSaving] = useState(false);

  async function handleSave() {
    setSaving(true);
    try {
      await onSave(text);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className={styles.verificationBox}>
      <p className={styles.verificationHint}>
        Vérification humaine — relisez et corrigez avant de passer à l&apos;étape suivante.
      </p>
      <textarea value={text} onChange={(e) => setText(e.target.value)} rows={10} />
      <button className="btn btn-primary" onClick={handleSave} disabled={saving} style={{ marginTop: 8 }}>
        {saving ? "Enregistrement…" : "Enregistrer la correction"}
      </button>
    </div>
  );
}
