"use client";

import { useEffect, useState } from "react";
import {
  Volume2, ExternalLink, Bot, Target, Headphones, BedDouble, PhoneIncoming,
  Smartphone, Lock, Clock, CheckCircle2, XCircle, Repeat, type LucideIcon,
} from "lucide-react";
import { useOrganization } from "@/lib/OrganizationContext";
import { api, Agent, AgentRequest } from "@/lib/api";
import { RetellTestCallWidget } from "@/components/RetellTestCallWidget";
import { AGENT_TEMPLATES } from "@/lib/agentTemplates";
import styles from "./agents.module.css";

interface CategoryAvatar {
  icon: LucideIcon;
  bg: string;
  color: string;
  label: string;
}

// Avatar par métier de l'agent (section 19/41) — l'icône reflète ce que fait
// l'agent, indépendamment du nom que le client choisit de lui donner
// ("Jean", "Sarah"...). Cohérent avec le vocabulaire déjà adapté par
// catégorie ailleurs dans le dashboard (Analytics, Tickets).
const CATEGORY_AVATARS: Record<string, CategoryAvatar> = {
  generique: { icon: Bot, bg: "var(--color-bg)", color: "var(--color-navy)", label: "Générique" },
  prospection: { icon: Target, bg: "var(--color-violet-soft)", color: "var(--color-violet)", label: "Prospection" },
  service_client: { icon: Headphones, bg: "var(--color-amber-soft)", color: "var(--color-amber)", label: "Service client" },
  hotellerie: { icon: BedDouble, bg: "var(--color-signal-soft)", color: "var(--color-signal)", label: "Hôtellerie" },
  telesecretariat: { icon: PhoneIncoming, bg: "var(--color-bg)", color: "var(--color-muted)", label: "Télésecrétariat" },
  telecom: { icon: Smartphone, bg: "var(--color-red-soft)", color: "var(--color-red)", label: "Télécom" },
  fidelisation: { icon: Repeat, bg: "var(--color-violet-soft)", color: "var(--color-violet)", label: "Fidélisation & Upsell" },
};

function getCategoryAvatar(category: string): CategoryAvatar {
  return CATEGORY_AVATARS[category] || CATEGORY_AVATARS.generique;
}

// Avatars personnages (choix stable par agent — basé sur son id, pas un
// vrai tirage aléatoire à chaque rendu, sinon l'avatar changerait à chaque
// rafraîchissement de la page).
const AVATAR_IMAGES = ["/avatars/avatar-1.jpg", "/avatars/avatar-2.jpg"];

function getAgentAvatarImage(agentId: string): string {
  let hash = 0;
  for (let i = 0; i < agentId.length; i++) {
    hash = (hash * 31 + agentId.charCodeAt(i)) % 1000;
  }
  return AVATAR_IMAGES[hash % AVATAR_IMAGES.length];
}

const REQUEST_STATUS_LABEL: Record<string, { label: string; icon: LucideIcon; color: string }> = {
  pending: { label: "En attente", icon: Clock, color: "var(--color-amber)" },
  in_progress: { label: "En cours de traitement", icon: Clock, color: "var(--color-violet)" },
  completed: { label: "Créé", icon: CheckCircle2, color: "var(--color-signal)" },
  rejected: { label: "Refusée", icon: XCircle, color: "var(--color-red)" },
};

export default function AgentsPage() {
  const { currentOrg } = useOrganization();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [requests, setRequests] = useState<AgentRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [testingAgentId, setTestingAgentId] = useState<string | null>(null);
  const [voiceEditAgentId, setVoiceEditAgentId] = useState<string | null>(null);
  const [voiceEditValue, setVoiceEditValue] = useState("");
  const [savingVoice, setSavingVoice] = useState(false);

  const [requestModalOpen, setRequestModalOpen] = useState(false);
  const [selectedTemplateKey, setSelectedTemplateKey] = useState<string>(AGENT_TEMPLATES[0].key);
  const [requestObjective, setRequestObjective] = useState("");
  const [submittingRequest, setSubmittingRequest] = useState(false);

  const load = () => {
    if (!currentOrg) return;
    setLoading(true);
    Promise.all([
      api.listAgents(currentOrg.organization_id),
      api.listAgentRequests(currentOrg.organization_id),
    ])
      .then(([a, r]) => {
        setAgents(a);
        setRequests(r);
      })
      .finally(() => setLoading(false));
  };

  useEffect(load, [currentOrg]);

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

  async function handleSubmitRequest(e: React.FormEvent) {
    e.preventDefault();
    if (!currentOrg || !requestObjective.trim()) return;
    setSubmittingRequest(true);
    try {
      await api.createAgentRequest(currentOrg.organization_id, {
        use_case: selectedTemplateKey,
        objective: requestObjective.trim(),
      });
      setRequestObjective("");
      setRequestModalOpen(false);
      load();
    } finally {
      setSubmittingRequest(false);
    }
  }

  if (!currentOrg) {
    return <p style={{ color: "var(--color-muted)" }}>Sélectionnez ou créez une organisation.</p>;
  }

  return (
    <div>
      <div className={styles.header}>
        <h1 className={styles.title}>Agents IA</h1>
        <button className={styles.button} onClick={() => setRequestModalOpen(true)}>
          + Demander un agent
        </button>
      </div>

      {loading ? (
        <p style={{ color: "var(--color-muted)" }}>Chargement…</p>
      ) : (
        <>
          {requests.length > 0 && (
            <div style={{ marginBottom: 28 }}>
              <h2 style={{ fontSize: 14, fontWeight: 600, color: "var(--color-muted)", marginBottom: 10, textTransform: "uppercase", letterSpacing: "0.03em" }}>
                Vos demandes
              </h2>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {requests.map((r) => {
                  const status = REQUEST_STATUS_LABEL[r.status] || REQUEST_STATUS_LABEL.pending;
                  const StatusIcon = status.icon;
                  const template = AGENT_TEMPLATES.find((t) => t.key === r.use_case);
                  return (
                    <div
                      key={r.id}
                      className="surface-card"
                      style={{ padding: "14px 18px", display: "flex", alignItems: "flex-start", gap: 12 }}
                    >
                      <StatusIcon size={16} color={status.color} style={{ marginTop: 2, flexShrink: 0 }} />
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                          <span style={{ fontWeight: 500, fontSize: 13.5 }}>{template?.label || r.use_case}</span>
                          <span style={{ fontSize: 11, fontFamily: "var(--font-mono)", color: status.color }}>{status.label}</span>
                        </div>
                        <p style={{ fontSize: 13, color: "var(--color-muted)", margin: 0 }}>{r.objective}</p>
                        {r.admin_notes && (
                          <p style={{ fontSize: 12.5, color: "var(--color-red)", marginTop: 6 }}>
                            Note : {r.admin_notes}
                          </p>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {agents.length === 0 ? (
            <p style={{ color: "var(--color-muted)" }}>
              Aucun agent pour cette organisation. Faites une demande avec le bouton ci-dessus — notre équipe le
              configure et le crée pour vous.
            </p>
          ) : (
            <div className={styles.grid}>
              {agents.map((agent) => {
                const avatar = getCategoryAvatar(agent.category);
                const avatarImage = getAgentAvatarImage(agent.id);
                return (
                  <div key={agent.id} className={styles.card}>
                    <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
                      <div style={{ position: "relative", flexShrink: 0 }}>
                        <div
                          style={{
                            width: 40, height: 40, borderRadius: "50%", overflow: "hidden",
                            border: "1px solid var(--color-line)", flexShrink: 0,
                          }}
                        >
                          {/* eslint-disable-next-line @next/next/no-img-element */}
                          <img src={avatarImage} alt={agent.name} width={40} height={40} style={{ objectFit: "cover", width: "100%", height: "100%" }} />
                        </div>
                        {agent.retell_agent_id && (
                          <div
                            title="Agent provisionné et actif chez Retell"
                            style={{
                              position: "absolute", bottom: -1, right: -1, width: 11, height: 11,
                              borderRadius: "50%", background: "var(--color-signal)",
                              border: "2px solid var(--color-surface)",
                            }}
                          />
                        )}
                      </div>
                      <div style={{ minWidth: 0 }}>
                        <div className={styles.cardName} style={{ marginBottom: 0 }}>{agent.name}</div>
                        <span style={{ fontSize: 11, color: "var(--color-muted)", fontFamily: "var(--font-mono)" }}>{avatar.label}</span>
                      </div>
                    </div>
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
                            border: "1px solid var(--color-signal)", color: "var(--color-signal)",
                            background: "transparent", borderRadius: "var(--radius-sm)", padding: "6px 12px", fontSize: 12,
                          }}
                        >
                          Tester en direct (voix)
                        </button>
                        <button
                          onClick={() => openVoiceEditor(agent)}
                          title={agent.voice_id ? `Voix actuelle : ${agent.voice_id}` : "Voix par défaut de la plateforme"}
                          style={{
                            border: "1px solid var(--color-line)", color: "var(--color-muted)", background: "transparent",
                            borderRadius: "var(--radius-sm)", padding: "6px 12px", fontSize: 12,
                            display: "inline-flex", alignItems: "center", gap: 5,
                          }}
                        >
                          <Volume2 size={12} /> Changer la voix
                        </button>
                      </div>
                    )}
                    {agent.retell_agent_id && (
                      <div
                        onClick={() => navigator.clipboard.writeText(agent.retell_agent_id!)}
                        title="Cliquer pour copier"
                        style={{
                          marginTop: 8, fontFamily: "var(--font-mono)", fontSize: 10.5, color: "var(--color-muted)",
                          cursor: "pointer", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                        }}
                      >
                        {agent.retell_agent_id}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}

      {requestModalOpen && (
        <div className={styles.modalOverlay} onClick={() => setRequestModalOpen(false)}>
          <form className={styles.modal} onClick={(e) => e.stopPropagation()} onSubmit={handleSubmitRequest}>
            <h2>Demander un agent</h2>
            <p className={styles.voiceHint} style={{ marginBottom: 4 }}>
              Décrivez votre besoin — notre équipe configure et crée l'agent pour vous, en s'appuyant sur nos
              modèles déjà éprouvés en conditions réelles.
            </p>

            <div>
              <label>Métier le plus proche de votre besoin</label>
              <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 6 }}>
                {AGENT_TEMPLATES.map((t) => (
                  <label
                    key={t.key}
                    style={{
                      display: "flex", alignItems: "flex-start", gap: 10, padding: "10px 12px",
                      border: "1px solid var(--color-line)", borderRadius: "var(--radius-sm)",
                      cursor: t.locked ? "not-allowed" : "pointer",
                      opacity: t.locked ? 0.5 : 1,
                      background: selectedTemplateKey === t.key && !t.locked ? "var(--color-bg)" : "transparent",
                    }}
                  >
                    <input
                      type="radio"
                      name="template"
                      value={t.key}
                      disabled={t.locked}
                      checked={selectedTemplateKey === t.key}
                      onChange={() => setSelectedTemplateKey(t.key)}
                      style={{ marginTop: 3 }}
                    />
                    <div style={{ flex: 1 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13.5, fontWeight: 500 }}>
                        {t.label}
                        {t.locked && (
                          <span
                            style={{
                              display: "inline-flex", alignItems: "center", gap: 4,
                              fontSize: 10, fontFamily: "var(--font-mono)", textTransform: "uppercase",
                              background: "var(--color-bg)", color: "var(--color-muted)",
                              padding: "2px 8px", borderRadius: 20,
                            }}
                          >
                            <Lock size={9} /> Bientôt
                          </span>
                        )}
                      </div>
                      <div style={{ fontSize: 12, color: "var(--color-muted)" }}>{t.description}</div>
                    </div>
                  </label>
                ))}
              </div>
            </div>

            <div>
              <label htmlFor="request-objective">Décrivez précisément votre besoin</label>
              <textarea
                id="request-objective"
                required
                rows={4}
                value={requestObjective}
                onChange={(e) => setRequestObjective(e.target.value)}
                placeholder="Ex. Un agent pour mon hôtel de 20 chambres à Dakar, qui gère les réservations et transfère les réclamations à la réception."
              />
            </div>

            <div className={styles.modalActions}>
              <button type="button" className={styles.cancelButton} onClick={() => setRequestModalOpen(false)}>
                Annuler
              </button>
              <button type="submit" className={styles.button} disabled={submittingRequest}>
                {submittingRequest ? "Envoi…" : "Envoyer la demande"}
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
