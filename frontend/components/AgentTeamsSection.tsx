"use client";

import { useEffect, useState } from "react";
import { Users, Plus, X, Pencil, Check, Phone, MessageCircle, Calendar, Clock } from "lucide-react";
import { api, Agent, AgentTeam, AgentTeamSummary } from "@/lib/api";
import styles from "./AgentTeamsSection.module.css";

interface Props {
  organizationId: string;
  agents: Agent[];
  onChange: () => void; // recharge la liste d'agents côté parent (team_id modifié)
}

export function AgentTeamsSection({ organizationId, agents, onChange }: Props) {
  const [teams, setTeams] = useState<AgentTeam[]>([]);
  const [summaries, setSummaries] = useState<Record<string, AgentTeamSummary>>({});
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [newTeamName, setNewTeamName] = useState("");
  const [editingTeamId, setEditingTeamId] = useState<string | null>(null);
  const [editingName, setEditingName] = useState("");

  const load = () => {
    setLoading(true);
    api.listAgentTeams(organizationId).then(async (list) => {
      setTeams(list);
      const entries = await Promise.all(
        list.map(async (t) => [t.id, await api.getTeamSummary(organizationId, t.id)] as const)
      );
      setSummaries(Object.fromEntries(entries));
    }).finally(() => setLoading(false));
  };

  useEffect(load, [organizationId]);

  async function handleCreateTeam(e: React.FormEvent) {
    e.preventDefault();
    if (!newTeamName.trim()) return;
    await api.createAgentTeam(organizationId, newTeamName.trim());
    setNewTeamName("");
    setCreating(false);
    load();
  }

  async function handleRename(teamId: string) {
    if (!editingName.trim()) return;
    await api.renameAgentTeam(organizationId, teamId, editingName.trim());
    setEditingTeamId(null);
    load();
  }

  async function handleDelete(teamId: string) {
    await api.deleteAgentTeam(organizationId, teamId);
    load();
    onChange();
  }

  async function handleAddAgent(teamId: string, agentId: string) {
    if (!agentId) return;
    await api.addAgentToTeam(organizationId, teamId, agentId);
    load();
    onChange();
  }

  async function handleRemoveAgent(teamId: string, agentId: string) {
    await api.removeAgentFromTeam(organizationId, teamId, agentId);
    load();
    onChange();
  }

  if (loading) return null;
  if (teams.length === 0 && !creating) {
    return (
      <div className={styles.emptyWrap}>
        <button className="btn btn-ghost" onClick={() => setCreating(true)}>
          <Users size={14} /> Créer une équipe
        </button>
      </div>
    );
  }

  return (
    <div className={styles.wrap}>
      <div className={styles.header}>
        <h2 className={styles.title}>Vos équipes</h2>
        {!creating && (
          <button className="btn btn-ghost" onClick={() => setCreating(true)}>
            <Plus size={14} /> Nouvelle équipe
          </button>
        )}
      </div>

      {creating && (
        <form className={styles.createForm} onSubmit={handleCreateTeam}>
          <input
            autoFocus
            placeholder="Nom de l'équipe (ex. Mon équipe commerciale)"
            value={newTeamName}
            onChange={(e) => setNewTeamName(e.target.value)}
          />
          <button type="submit" className="btn btn-primary">Créer</button>
          <button type="button" className="btn btn-ghost" onClick={() => { setCreating(false); setNewTeamName(""); }}>
            Annuler
          </button>
        </form>
      )}

      <div className={styles.teamGrid}>
        {teams.map((team) => {
          const summary = summaries[team.id];
          const memberAgents = agents.filter((a) => team.agent_ids.includes(a.id));
          const availableAgents = agents.filter((a) => !a.team_id || a.team_id === team.id).filter((a) => !team.agent_ids.includes(a.id));

          return (
            <div key={team.id} className={styles.teamCard}>
              <div className={styles.teamHeader}>
                {editingTeamId === team.id ? (
                  <div className={styles.renameRow}>
                    <input value={editingName} onChange={(e) => setEditingName(e.target.value)} autoFocus />
                    <button onClick={() => handleRename(team.id)}><Check size={14} /></button>
                  </div>
                ) : (
                  <div className={styles.teamName}>
                    <Users size={15} />
                    {team.name}
                    <button className={styles.iconButton} onClick={() => { setEditingTeamId(team.id); setEditingName(team.name); }}>
                      <Pencil size={12} />
                    </button>
                  </div>
                )}
                <button className={styles.iconButton} onClick={() => handleDelete(team.id)} title="Dissoudre l'équipe">
                  <X size={14} />
                </button>
              </div>

              {summary && (
                <div className={styles.summaryRow}>
                  <div className={styles.summaryItem}>
                    <Phone size={13} /> <strong>{summary.total_calls}</strong> appels
                  </div>
                  <div className={styles.summaryItem}>
                    <Clock size={13} /> <strong>{summary.total_call_minutes}</strong> min
                  </div>
                  <div className={styles.summaryItem}>
                    <MessageCircle size={13} /> <strong>{summary.total_whatsapp_messages}</strong> WhatsApp
                  </div>
                  <div className={styles.summaryItem}>
                    <Calendar size={13} /> <strong>{summary.total_appointments}</strong> RDV
                  </div>
                </div>
              )}
              <p className={styles.summaryHint}>Sur les 30 derniers jours, tous les agents de l'équipe combinés</p>

              <div className={styles.members}>
                {memberAgents.map((a) => (
                  <span key={a.id} className={styles.memberChip}>
                    {a.name}
                    <button onClick={() => handleRemoveAgent(team.id, a.id)}><X size={11} /></button>
                  </span>
                ))}
                {memberAgents.length === 0 && <span className={styles.noMembers}>Aucun agent pour l'instant</span>}
              </div>

              {availableAgents.length > 0 && (
                <select
                  className={styles.addSelect}
                  value=""
                  onChange={(e) => handleAddAgent(team.id, e.target.value)}
                >
                  <option value="">+ Ajouter un agent…</option>
                  {availableAgents.map((a) => (
                    <option key={a.id} value={a.id}>{a.name}</option>
                  ))}
                </select>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
