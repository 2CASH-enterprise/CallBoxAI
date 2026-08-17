"use client";

import { useEffect, useState } from "react";
import { useOrganization } from "@/lib/OrganizationContext";
import { api, Agent, Call } from "@/lib/api";
import styles from "./calls.module.css";

export default function CallsPage() {
  const { currentOrg } = useOrganization();
  const [calls, setCalls] = useState<Call[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [selectedAgent, setSelectedAgent] = useState("");
  const [toNumber, setToNumber] = useState("+221770000000");
  const [loading, setLoading] = useState(true);
  const [simulating, setSimulating] = useState(false);

  const load = () => {
    if (!currentOrg) return;
    setLoading(true);
    Promise.all([api.listCalls(currentOrg.id), api.listAgents(currentOrg.id)])
      .then(([c, a]) => {
        setCalls(c);
        setAgents(a);
        if (a.length > 0 && !selectedAgent) setSelectedAgent(a[0].id);
      })
      .finally(() => setLoading(false));
  };

  useEffect(load, [currentOrg]);

  async function handleSimulate() {
    if (!currentOrg || !selectedAgent) return;
    setSimulating(true);
    try {
      await api.createCall(currentOrg.id, {
        agent_id: selectedAgent,
        to_number: toNumber,
        from_number: "+221780000000",
        direction: "outbound",
      });
      load();
    } finally {
      setSimulating(false);
    }
  }

  if (!currentOrg) {
    return <p style={{ color: "var(--color-muted)" }}>Sélectionnez ou créez une organisation.</p>;
  }

  return (
    <div>
      <div className={styles.header}>
        <h1 className={styles.title}>Appels</h1>
      </div>

      <div className={styles.simulateBar}>
        {agents.length === 0 ? (
          <span className={styles.mockNote}>
            Créez d'abord un agent pour pouvoir simuler un appel.
          </span>
        ) : (
          <>
            <select value={selectedAgent} onChange={(e) => setSelectedAgent(e.target.value)}>
              {agents.map((a) => (
                <option key={a.id} value={a.id}>{a.name}</option>
              ))}
            </select>
            <input value={toNumber} onChange={(e) => setToNumber(e.target.value)} placeholder="Numéro appelé" />
            <span className={styles.mockNote}>mode Mock — sans coût</span>
            <button onClick={handleSimulate} disabled={simulating}>
              {simulating ? "Appel en cours…" : "Simuler un appel"}
            </button>
          </>
        )}
      </div>

      <div className={styles.table}>
        <div className={`${styles.row} ${styles.rowHead}`}>
          <span>Sens</span>
          <span>Résumé</span>
          <span>Transcript</span>
          <span>Statut</span>
        </div>
        {loading ? (
          <div className={styles.emptyState}>Chargement…</div>
        ) : calls.length === 0 ? (
          <div className={styles.emptyState}>Aucun appel enregistré pour l'instant.</div>
        ) : (
          calls.map((call) => (
            <div key={call.id} className={styles.row}>
              <span>{call.direction === "inbound" ? "Entrant" : "Sortant"}</span>
              <span>{call.summary}</span>
              <span className={styles.transcript}>{call.transcript}</span>
              <span>{call.status}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
