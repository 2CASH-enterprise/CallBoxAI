"use client";

import { useEffect, useState } from "react";
import { Sparkles, Volume2, ExternalLink } from "lucide-react";
import { useOrganization } from "@/lib/OrganizationContext";
import { api, Agent } from "@/lib/api";
import { RetellTestCallWidget } from "@/components/RetellTestCallWidget";
import styles from "./agents.module.css";

const LANGUAGES = [
  { value: "fr", label: "Français" },
  { value: "wo", label: "Wolof" },
  { value: "en", label: "Anglais" },
  { value: "multi", label: "Multilingue (détection automatique)" },
];

export default function AgentsPage() {
  const { currentOrg } = useOrganization();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [testingAgentId, setTestingAgentId] = useState<string | null>(null);
  const [voiceEditAgentId, setVoiceEditAgentId] = useState<string | null>(null);
  const [voiceEditValue, setVoiceEditValue] = useState("");
  const [savingVoice, setSavingVoice] = useState(false);
  const [form, setForm] = useState({
    name: "", objective: "", system_prompt: "", language: "fr",
    transfer_enabled: false, transfer_number: "", transfer_instructions: "", voice_id: "", business_hours_start: "", business_hours_end: "", ticketing_enabled: false,
  });
  const [submitting, setSubmitting] = useState(false);

  const load = () => {
    if (!currentOrg) return;
    setLoading(true);
    api.listAgents(currentOrg.organization_id).then(setAgents).finally(() => setLoading(false));
  };

  useEffect(load, [currentOrg]);

  function useProspectionTemplate() {
    setForm({
      name: "Agent Prospection Commerciale",
      objective: "Qualifier les prospects et prendre des rendez-vous",
      system_prompt:
        "Tu es l'assistant commercial de l'entreprise.\n\n" +
        "Ton objectif est de qualifier les prospects et de prendre des rendez-vous.\n\n" +
        "Tu dois toujours :\n" +
        "- être poli ;\n" +
        "- parler naturellement ;\n" +
        "- poser les questions dans l'ordre : besoin, budget, échéance ;\n" +
        "- ne jamais inventer une information ;\n" +
        "- proposer un rendez-vous dès que le prospect montre de l'intérêt ;\n" +
        "- transférer au responsable commercial lorsqu'une demande dépasse tes compétences " +
        "(négociation tarifaire complexe, réclamation, demande hors sujet).",
      language: "fr",
      transfer_enabled: true,
      transfer_number: "+221339000000",
      transfer_instructions: "Négociation tarifaire complexe, réclamation, ou demande hors du champ commercial standard.",
      voice_id: "",
      business_hours_start: "",
      business_hours_end: "",
      ticketing_enabled: false,
    });
    setModalOpen(true);
  }

  function useServiceClientTemplate() {
    setForm({
      name: "Agent Service Client",
      objective: "Répondre aux demandes de niveau 1 et escalader si besoin",
      system_prompt:
        "Tu es l'assistant du service client de l'entreprise.\n\n" +
        "Ton objectif est de répondre aux questions courantes (horaires, tarifs, suivi de dossier) " +
        "en t'appuyant sur la base de connaissances, et de résoudre les demandes de premier niveau.\n\n" +
        "Tu dois toujours :\n" +
        "- être poli et rassurant, surtout si le client est mécontent ;\n" +
        "- vérifier la base de connaissances avant de répondre ;\n" +
        "- ne jamais inventer une information ;\n" +
        "- consigner clairement le motif de l'appel pour le suivi ;\n" +
        "- transférer au responsable dès que la demande dépasse tes compétences " +
        "(réclamation grave, litige, demande juridique).",
      language: "fr",
      transfer_enabled: true,
      transfer_number: "+221339000000",
      transfer_instructions: "Réclamation grave, litige, ou demande dépassant le support de niveau 1.",
      voice_id: "",
      business_hours_start: "08:00",
      business_hours_end: "18:00",
      ticketing_enabled: true,
    });
    setModalOpen(true);
  }

  function useHotelReceptionistTemplate() {
    setForm({
      name: "Agent Réceptionniste Hôtel",
      objective: "Répondre aux demandes des clients et de l'hôtel, prendre les réservations, transférer si besoin",
      system_prompt:
        "Tu es la réceptionniste virtuelle de l'hôtel.\n\n" +
        "Ton objectif est de répondre aux demandes des clients (informations, réservations, questions " +
        "pratiques) et de transférer à la réception physique quand une intervention humaine est nécessaire.\n\n" +
        "Tu dois toujours :\n" +
        "- accueillir chaleureusement, en français ou en anglais selon la langue du client ;\n" +
        "- t'appuyer sur la base de connaissances pour les horaires, tarifs, équipements, politique d'annulation ;\n" +
        "- ne jamais inventer une disponibilité ou un tarif que tu ne connais pas ;\n" +
        "- proposer une réservation dès que le client exprime une intention claire de dates ;\n" +
        "- transférer à la réception pour : une modification de réservation existante, une réclamation, " +
        "ou toute demande urgente (problème dans la chambre, sécurité) ;\n" +
        "- rester concise, les clients appellent souvent depuis leur téléphone en déplacement.",
      language: "multi",
      transfer_enabled: true,
      transfer_number: "+33100000000",
      transfer_instructions: "Modification de réservation existante, réclamation, ou demande urgente (chambre, sécurité).",
      voice_id: "",
      business_hours_start: "",
      business_hours_end: "",
      ticketing_enabled: true,
    });
    setModalOpen(true);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!currentOrg || !form.name.trim()) return;
    setSubmitting(true);
    try {
      await api.createAgent(currentOrg.organization_id, form);
      setForm({
        name: "", objective: "", system_prompt: "", language: "fr",
        transfer_enabled: false, transfer_number: "", transfer_instructions: "", voice_id: "", business_hours_start: "", business_hours_end: "", ticketing_enabled: false,
      });
      setModalOpen(false);
      load();
    } finally {
      setSubmitting(false);
    }
  }

  function openVoiceEditor(agent: Agent) {
    setVoiceEditAgentId(agent.id);
    setVoiceEditValue(agent.voice_id || "");
  }

  async function handleSaveVoice() {
    if (!currentOrg || !voiceEditAgentId || !voiceEditValue.trim()) return;
    setSavingVoice(true);
    try {
      await api.updateAgent(currentOrg.organization_id, voiceEditAgentId, { voice_id: voiceEditValue.trim() });
      setVoiceEditAgentId(null);
      load();
    } finally {
      setSavingVoice(false);
    }
  }

  if (!currentOrg) {
    return <p style={{ color: "var(--color-muted)" }}>Sélectionnez ou créez une organisation.</p>;
  }

  return (
    <div>
      <div className={styles.header}>
        <h1 className={styles.title}>Agents IA</h1>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn btn-ghost" onClick={useProspectionTemplate}>
            <Sparkles size={14} /> Modèle : Prospection commerciale
          </button>
          <button className="btn btn-ghost" onClick={useServiceClientTemplate}>
            <Sparkles size={14} /> Modèle : Service Client
          </button>
          <button className="btn btn-ghost" onClick={useHotelReceptionistTemplate}>
            <Sparkles size={14} /> Modèle : Réceptionniste Hôtel
          </button>
          <button className={styles.button} onClick={() => setModalOpen(true)}>
            + Créer un agent
          </button>
        </div>
      </div>

      {loading ? (
        <p style={{ color: "var(--color-muted)" }}>Chargement…</p>
      ) : agents.length === 0 ? (
        <p style={{ color: "var(--color-muted)" }}>
          Aucun agent pour cette organisation. Créez le premier avec le bouton ci-dessus.
        </p>
      ) : (
        <div className={styles.grid}>
          {agents.map((agent) => (
            <div key={agent.id} className={styles.card}>
              <div className={styles.cardName}>{agent.name}</div>
              <div className={styles.cardObjective}>{agent.objective || "Objectif non défini"}</div>
              <span className={styles.langTag}>{agent.language}</span>
              {agent.transfer_enabled && (
                <span className={styles.langTag} style={{ marginLeft: 6, background: "var(--color-amber-soft)", color: "var(--color-amber)" }}>
                  Transfert activé
                </span>
              )}
              {agent.retell_agent_id && (
                <div style={{ marginTop: 10, display: "flex", gap: 6, flexWrap: "wrap" }}>
                  <button
                    onClick={() => setTestingAgentId(agent.id)}
                    style={{
                      border: "1px solid var(--color-signal)",
                      color: "var(--color-signal)",
                      background: "transparent",
                      borderRadius: "var(--radius-sm)",
                      padding: "6px 12px",
                      fontSize: 12,
                    }}
                  >
                    Tester en direct (voix)
                  </button>
                  <button
                    onClick={() => openVoiceEditor(agent)}
                    title={agent.voice_id ? `Voix actuelle : ${agent.voice_id}` : "Voix par défaut de la plateforme"}
                    style={{
                      border: "1px solid var(--color-line)",
                      color: "var(--color-muted)",
                      background: "transparent",
                      borderRadius: "var(--radius-sm)",
                      padding: "6px 12px",
                      fontSize: 12,
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 5,
                    }}
                  >
                    <Volume2 size={12} /> Changer la voix
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {modalOpen && (
        <div className={styles.modalOverlay} onClick={() => setModalOpen(false)}>
          <form className={styles.modal} onClick={(e) => e.stopPropagation()} onSubmit={handleSubmit}>
            <h2>Nouvel agent IA</h2>

            <div>
              <label htmlFor="agent-name">Nom</label>
              <input
                id="agent-name"
                required
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="Agent commercial"
              />
            </div>

            <div>
              <label htmlFor="agent-objective">Objectif</label>
              <input
                id="agent-objective"
                value={form.objective}
                onChange={(e) => setForm({ ...form, objective: e.target.value })}
                placeholder="Qualifier les prospects et prendre des rendez-vous"
              />
            </div>

            <div>
              <label htmlFor="agent-language">Langue</label>
              <select
                id="agent-language"
                value={form.language}
                onChange={(e) => setForm({ ...form, language: e.target.value })}
              >
                {LANGUAGES.map((l) => (
                  <option key={l.value} value={l.value}>{l.label}</option>
                ))}
              </select>
              {form.language === "multi" && (
                <p className={styles.voiceHint}>
                  L'agent détecte automatiquement la langue de l'appelant parmi 55 langues supportées par
                  Retell. La qualité de la voix peut varier selon la langue parlée — certaines voix sont
                  optimisées pour une langue en particulier.
                </p>
              )}
            </div>

            <div>
              <label htmlFor="agent-prompt">Prompt système</label>
              <textarea
                id="agent-prompt"
                rows={4}
                value={form.system_prompt}
                onChange={(e) => setForm({ ...form, system_prompt: e.target.value })}
                placeholder="Tu es l'assistant commercial de l'entreprise…"
              />
            </div>

            <div>
              <label htmlFor="agent-voice">Voix (optionnel)</label>
              <input
                id="agent-voice"
                value={form.voice_id}
                onChange={(e) => setForm({ ...form, voice_id: e.target.value })}
                placeholder="Ex. 11labs-Charlotte"
              />
              <p className={styles.voiceHint}>
                Ouvrez l'onglet <strong>Voices</strong> du{" "}
                <a href="https://dashboard.retellai.com" target="_blank" rel="noreferrer">
                  dashboard Retell <ExternalLink size={11} style={{ verticalAlign: "-1px" }} />
                </a>{" "}
                , filtrez par langue française, écoutez un échantillon, puis collez ici l'identifiant de la voix
                qui vous plaît. Laissez vide pour la voix par défaut.
              </p>
            </div>

            <div>
              <label>Horaires d'ouverture (télé-secrétariat, optionnel)</label>
              <div style={{ display: "flex", gap: 8 }}>
                <input
                  type="time"
                  value={form.business_hours_start}
                  onChange={(e) => setForm({ ...form, business_hours_start: e.target.value })}
                />
                <input
                  type="time"
                  value={form.business_hours_end}
                  onChange={(e) => setForm({ ...form, business_hours_end: e.target.value })}
                />
              </div>
              <p className={styles.voiceHint}>
                En dehors de cette plage, un appel entrant déclenche automatiquement une prise de message
                plutôt qu'une conversation. Laissez vide pour un agent disponible en permanence.
              </p>
            </div>

            <div>
              <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
                <input
                  type="checkbox"
                  checked={form.ticketing_enabled}
                  onChange={(e) => setForm({ ...form, ticketing_enabled: e.target.checked })}
                />
                Activer le service client (crée un ticket de suivi pour chaque appel entrant)
              </label>
            </div>

            <div>
              <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
                <input
                  type="checkbox"
                  checked={form.transfer_enabled}
                  onChange={(e) => setForm({ ...form, transfer_enabled: e.target.checked })}
                />
                Activer le transfert vers un opérateur humain
              </label>
            </div>

            {form.transfer_enabled && (
              <>
                <div>
                  <label htmlFor="agent-transfer-number">Numéro de l'opérateur</label>
                  <input
                    id="agent-transfer-number"
                    value={form.transfer_number}
                    onChange={(e) => setForm({ ...form, transfer_number: e.target.value })}
                    placeholder="+221339000000"
                  />
                </div>
                <div>
                  <label htmlFor="agent-transfer-instructions">Dans quels cas transférer ? (optionnel)</label>
                  <input
                    id="agent-transfer-instructions"
                    value={form.transfer_instructions}
                    onChange={(e) => setForm({ ...form, transfer_instructions: e.target.value })}
                    placeholder="Ex. demande de remboursement, réclamation complexe"
                  />
                </div>
              </>
            )}

            <div className={styles.modalActions}>
              <button type="button" className={styles.cancelButton} onClick={() => setModalOpen(false)}>
                Annuler
              </button>
              <button type="submit" className={styles.button} disabled={submitting}>
                {submitting ? "Création…" : "Créer l'agent"}
              </button>
            </div>
          </form>
        </div>
      )}

      {voiceEditAgentId && (
        <div className={styles.modalOverlay} onClick={() => setVoiceEditAgentId(null)}>
          <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
            <h2>Changer la voix</h2>
            <p className={styles.voiceHint} style={{ marginBottom: 12 }}>
              Ouvrez l'onglet <strong>Voices</strong> du{" "}
              <a href="https://dashboard.retellai.com" target="_blank" rel="noreferrer">
                dashboard Retell <ExternalLink size={11} style={{ verticalAlign: "-1px" }} />
              </a>{" "}
              , filtrez par langue française, écoutez les échantillons, et collez ici l'identifiant de la voix
              retenue. Le changement s'applique à partir du prochain test/appel.
            </p>
            <input
              value={voiceEditValue}
              onChange={(e) => setVoiceEditValue(e.target.value)}
              placeholder="Ex. 11labs-Charlotte"
              autoFocus
            />
            <div className={styles.modalActions}>
              <button type="button" className={styles.cancelButton} onClick={() => setVoiceEditAgentId(null)}>
                Annuler
              </button>
              <button type="button" className={styles.button} onClick={handleSaveVoice} disabled={savingVoice}>
                {savingVoice ? "Enregistrement…" : "Enregistrer"}
              </button>
            </div>
          </div>
        </div>
      )}

      {testingAgentId && currentOrg && (
        <RetellTestCallWidget
          organizationId={currentOrg.organization_id}
          agentId={testingAgentId}
          onClose={() => setTestingAgentId(null)}
        />
      )}
    </div>
  );
}
