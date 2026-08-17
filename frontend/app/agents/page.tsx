"use client";

import { useEffect, useState } from "react";
import { useOrganization } from "@/lib/OrganizationContext";
import { api, Agent } from "@/lib/api";
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
  const [form, setForm] = useState({ name: "", objective: "", system_prompt: "", language: "fr" });
  const [submitting, setSubmitting] = useState(false);

  const load = () => {
    if (!currentOrg) return;
    setLoading(true);
    api.listAgents(currentOrg.id).then(setAgents).finally(() => setLoading(false));
  };

  useEffect(load, [currentOrg]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!currentOrg || !form.name.trim()) return;
    setSubmitting(true);
    try {
      await api.createAgent(currentOrg.id, form);
      setForm({ name: "", objective: "", system_prompt: "", language: "fr" });
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
    </div>
  );
}
