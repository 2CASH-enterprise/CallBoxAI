"use client";

import { useEffect, useState } from "react";
import { Plus, Trash2, PhoneCall } from "lucide-react";
import { useOrganization } from "@/lib/OrganizationContext";
import { api, Agent, Contact, Survey, SurveyQuestion, SurveyResults } from "@/lib/api";
import styles from "./surveys.module.css";

let questionCounter = 0;
function newQuestionId() {
  questionCounter += 1;
  return `q${questionCounter}_${Date.now()}`;
}

export default function SurveysPage() {
  const { currentOrg } = useOrganization();
  const [surveys, setSurveys] = useState<Survey[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [results, setResults] = useState<SurveyResults | null>(null);

  const [modalOpen, setModalOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [agentId, setAgentId] = useState("");
  const [questions, setQuestions] = useState<SurveyQuestion[]>([
    { id: newQuestionId(), text: "", type: "rating" },
  ]);
  const [submitting, setSubmitting] = useState(false);

  const [callContactId, setCallContactId] = useState("");
  const [callingSurvey, setCallingSurvey] = useState(false);

  const loadSurveys = () => {
    if (!currentOrg) return;
    Promise.all([api.listSurveys(currentOrg.organization_id), api.listAgents(currentOrg.organization_id), api.listContacts(currentOrg.organization_id)])
      .then(([s, a, c]) => {
        setSurveys(s);
        setAgents(a);
        setContacts(c);
        if (a.length > 0) setAgentId((prev) => prev || a[0].id);
        if (c.length > 0) setCallContactId((prev) => prev || c[0].id);
        if (!selectedId && s.length > 0) setSelectedId(s[0].id);
      });
  };

  useEffect(loadSurveys, [currentOrg]);

  const loadResults = () => {
    if (!currentOrg || !selectedId) return;
    api.getSurveyResults(currentOrg.organization_id, selectedId).then(setResults);
  };

  useEffect(loadResults, [selectedId, currentOrg]);

  function addQuestion() {
    setQuestions([...questions, { id: newQuestionId(), text: "", type: "rating" }]);
  }

  function updateQuestion(id: string, patch: Partial<SurveyQuestion>) {
    setQuestions(questions.map((q) => (q.id === id ? { ...q, ...patch } : q)));
  }

  function removeQuestion(id: string) {
    setQuestions(questions.filter((q) => q.id !== id));
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!currentOrg || !title.trim() || !agentId || questions.length === 0) return;
    setSubmitting(true);
    try {
      const created = await api.createSurvey(currentOrg.organization_id, {
        title: title.trim(),
        agent_id: agentId,
        questions: questions.map((q) => ({
          ...q,
          options: q.type === "choice" ? (q.options || []).filter(Boolean) : undefined,
        })),
      });
      setTitle("");
      setQuestions([{ id: newQuestionId(), text: "", type: "rating" }]);
      setModalOpen(false);
      setSurveys((prev) => [...prev, created]);
      setSelectedId(created.id);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleCall() {
    if (!currentOrg || !selectedId || !callContactId) return;
    const contact = contacts.find((c) => c.id === callContactId);
    if (!contact) return;
    setCallingSurvey(true);
    try {
      await api.callForSurvey(currentOrg.organization_id, selectedId, { contact_id: contact.id, to_number: contact.phone });
      loadResults();
    } finally {
      setCallingSurvey(false);
    }
  }

  if (!currentOrg) {
    return <p style={{ color: "var(--color-muted)" }}>Sélectionnez ou créez une organisation.</p>;
  }

  const selectedSurvey = surveys.find((s) => s.id === selectedId);

  return (
    <div>
      <div className={styles.header}>
        <h1 className={styles.title}>Sondages</h1>
        <button className="btn btn-primary" onClick={() => setModalOpen(true)} disabled={agents.length === 0}>
          <Plus size={14} /> Nouveau sondage
        </button>
      </div>

      <div className={styles.layout}>
        <div className={styles.panel}>
          <div className={styles.panelHeader}>Vos sondages</div>
          {surveys.length === 0 ? (
            <div className={styles.emptyState}>Aucun sondage pour l'instant.</div>
          ) : (
            surveys.map((s) => (
              <button
                key={s.id}
                className={`${styles.surveyItem} ${selectedId === s.id ? styles.surveyItemActive : ""}`}
                onClick={() => setSelectedId(s.id)}
              >
                {s.title}
              </button>
            ))
          )}
        </div>

        <div>
          {!selectedSurvey ? (
            <p style={{ color: "var(--color-muted)" }}>Créez ou sélectionnez un sondage.</p>
          ) : (
            <>
              <div className={styles.section}>
                <div className={styles.sectionHeader}>
                  <span>Simuler un appel de sondage</span>
                </div>
                {contacts.length === 0 ? (
                  <p style={{ fontSize: 13, color: "var(--color-muted)" }}>
                    Ajoutez d'abord des contacts pour pouvoir les appeler.
                  </p>
                ) : (
                  <div style={{ display: "flex", gap: 8 }}>
                    <select value={callContactId} onChange={(e) => setCallContactId(e.target.value)} style={{ flex: 1 }}>
                      {contacts.map((c) => (
                        <option key={c.id} value={c.id}>
                          {[c.first_name, c.last_name].filter(Boolean).join(" ") || c.phone}
                        </option>
                      ))}
                    </select>
                    <button className="btn btn-signal" onClick={handleCall} disabled={callingSurvey}>
                      <PhoneCall size={14} /> {callingSurvey ? "Appel…" : "Appeler"}
                    </button>
                  </div>
                )}
              </div>

              <div className={styles.section}>
                <div className={styles.sectionHeader}>
                  <span>Résultats ({results?.total_responses ?? 0} réponse(s))</span>
                </div>
                {!results || results.total_responses === 0 ? (
                  <div className={styles.emptyState}>Aucune réponse pour l'instant.</div>
                ) : (
                  results.results.map((r) => (
                    <div key={r.question_id} className={styles.questionResult}>
                      <div className={styles.questionText}>{r.question_text}</div>
                      {r.type === "choice" &&
                        Object.entries(r.summary).map(([option, count]) => {
                          const max = Math.max(...Object.values(r.summary).map((v) => Number(v)), 1);
                          return (
                            <div key={option} className={styles.barRow}>
                              <span className={styles.barLabel}>{option}</span>
                              <div className={styles.barTrack}>
                                <div className={styles.barFill} style={{ width: `${(Number(count) / max) * 100}%` }} />
                              </div>
                              <span className={styles.barCount}>{count}</span>
                            </div>
                          );
                        })}
                      {r.type === "rating" && (
                        <div>
                          <span className={styles.ratingValue}>{r.summary.average}</span>
                          <span className={styles.ratingSub}> / 5 · {r.summary.count} réponse(s)</span>
                        </div>
                      )}
                      {r.type === "open" &&
                        (r.summary.responses as string[]).map((resp, i) => (
                          <div key={i} className={styles.openResponse}>{resp}</div>
                        ))}
                    </div>
                  ))
                )}
              </div>
            </>
          )}
        </div>
      </div>

      {modalOpen && (
        <div className={styles.modalOverlay} onClick={() => setModalOpen(false)}>
          <form className={styles.modal} onClick={(e) => e.stopPropagation()} onSubmit={handleCreate}>
            <h2>Nouveau sondage</h2>
            <div className={styles.form}>
              <input placeholder="Titre du sondage" value={title} onChange={(e) => setTitle(e.target.value)} required />
              <select value={agentId} onChange={(e) => setAgentId(e.target.value)} required>
                {agents.map((a) => (
                  <option key={a.id} value={a.id}>{a.name}</option>
                ))}
              </select>

              {questions.map((q, i) => (
                <div key={q.id} className={styles.questionCard}>
                  <div className={styles.questionRow}>
                    <input
                      placeholder={`Question ${i + 1}`}
                      value={q.text}
                      onChange={(e) => updateQuestion(q.id, { text: e.target.value })}
                      required
                    />
                    <select value={q.type} onChange={(e) => updateQuestion(q.id, { type: e.target.value as SurveyQuestion["type"] })}>
                      <option value="rating">Note (1-5)</option>
                      <option value="choice">Choix</option>
                      <option value="open">Libre</option>
                    </select>
                  </div>
                  {q.type === "choice" && (
                    <input
                      placeholder="Options séparées par des virgules (ex. Oui, Non, Sans avis)"
                      value={(q.options || []).join(", ")}
                      onChange={(e) => updateQuestion(q.id, { options: e.target.value.split(",").map((o) => o.trim()) })}
                    />
                  )}
                  {questions.length > 1 && (
                    <button type="button" className={styles.removeButton} onClick={() => removeQuestion(q.id)}>
                      <Trash2 size={12} /> Retirer
                    </button>
                  )}
                </div>
              ))}

              <button type="button" className="btn btn-ghost" onClick={addQuestion} style={{ alignSelf: "flex-start" }}>
                <Plus size={13} /> Ajouter une question
              </button>
            </div>
            <div className={styles.modalActions}>
              <button type="button" className="btn btn-ghost" onClick={() => setModalOpen(false)}>
                Annuler
              </button>
              <button type="submit" className="btn btn-primary" disabled={submitting}>
                {submitting ? "Création…" : "Créer le sondage"}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
