"use client";

import { useEffect, useState } from "react";
import { useOrganization } from "@/lib/OrganizationContext";
import { api, Agent } from "@/lib/api";
import { RetellTestCallWidget } from "@/components/RetellTestCallWidget";
import styles from "./agents.module.css";

const LANGUAGES = [
  { value: "fr", label: "Français" },
  { value: "wo", label: "Wolof" },
  { value: "en", label: "Anglais" },
];

export default function AgentsPage() {
  const { currentOrg } = useOrganization();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [testingAgentId, setTestingAgentId] = useState<string | null>(null);
  const [form, setForm] = useState({
    name: "", objective: "", system_prompt: "", language: "fr",
    transfer_enabled: false, transfer_number: "", transfer_instructions: "",
    retell_agent_id: "",
  });
  const [submitting, setSubmitting] = useState(false);

  const load = () => {
    if (!currentOrg) return;
    setLoading(true);
    api.listAgents(currentOrg.organization_id).then(setAgents).finally(() => setLoading(false));
  };

  useEffect(load, [currentOrg]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!currentOrg || !form.name.trim()) return;
    setSubmitting(true);
    try {
      await api.createAgent(currentOrg.organization_id, form);
      setForm({
        name: "", objective: "", system_prompt: "", language: "fr",
        transfer_enabled: false, transfer_number: "", transfer_instructions: "",
        retell_agent_id: "",
      });
      setModalOpen(false);
      load();
    } finally {
      setSubmitting(false);
    }
  }

  if (!currentOrg) {
    return <p style={{ color: "var(--color-muted)" }}>Sélectionnez ou créez une organisation.</p>;
  }

  return (
    <div>
      <div className={styles.header}>
        <h1 className={styles.title}>Agents IA</h1>
        <button className={styles.button} onClick={() => setModalOpen(true)}>
          + Créer un agent
        </button>
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
                <div style={{ marginTop: 10 }}>
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
              <label htmlFor="agent-retell-id">ID agent Retell (optionnel, pour le test vocal en direct)</label>
              <input
                id="agent-retell-id"
                value={form.retell_agent_id}
                onChange={(e) => setForm({ ...form, retell_agent_id: e.target.value })}
                placeholder="agent_xxxxxxxxxxxx (créé dans le dashboard Retell)"
              />
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
