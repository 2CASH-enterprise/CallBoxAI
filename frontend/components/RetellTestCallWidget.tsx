"use client";

/**
 * Widget de test vocal en direct (Web Call Retell, section 16 du cahier des
 * charges). Établit une connexion WebRTC directement dans le navigateur —
 * aucun numéro de téléphone, aucun Twilio nécessaire pour ce test.
 */
import { useEffect, useRef, useState } from "react";
import { RetellWebClient } from "retell-client-js-sdk";
import { api, ApiError } from "@/lib/api";
import styles from "./RetellTestCallWidget.module.css";

interface TranscriptTurn {
  role: string;
  content: string;
}

type CallState = "idle" | "connecting" | "active" | "ended" | "error";

export function RetellTestCallWidget({
  organizationId,
  agentId,
  onClose,
}: {
  organizationId: string;
  agentId: string;
  onClose: () => void;
}) {
  const [state, setState] = useState<CallState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [transcript, setTranscript] = useState<TranscriptTurn[]>([]);
  const [agentTalking, setAgentTalking] = useState(false);
  const clientRef = useRef<RetellWebClient | null>(null);

  useEffect(() => {
    const client = new RetellWebClient();
    clientRef.current = client;

    client.on("call_started", () => setState("active"));
    client.on("call_ended", () => setState("ended"));
    client.on("agent_start_talking", () => setAgentTalking(true));
    client.on("agent_stop_talking", () => setAgentTalking(false));
    client.on("error", (message: string) => {
      setError(message || "Erreur pendant l'appel");
      setState("error");
      client.stopCall();
    });
    client.on("update", (payload: { transcript?: TranscriptTurn[] }) => {
      if (payload.transcript) setTranscript(payload.transcript);
    });

    return () => {
      client.stopCall();
    };
  }, []);

  async function handleStart() {
    setError(null);
    setState("connecting");
    try {
      const { access_token } = await api.createAgentTestCall(organizationId, agentId);
      await clientRef.current?.startCall({ accessToken: access_token });
    } catch (e) {
      const message = e instanceof ApiError ? e.message : "Impossible de démarrer le test vocal.";
      setError(message);
      setState("error");
    }
  }

  function handleStop() {
    clientRef.current?.stopCall();
    setState("ended");
  }

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.panel} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <h2>Test vocal en direct</h2>
          <button className={styles.closeButton} onClick={onClose}>×</button>
        </div>

        <p className={styles.hint}>
          Appel via votre micro/haut-parleur, dans le navigateur — aucun numéro de téléphone,
          aucun coût Twilio pour ce test.
        </p>

        {error && <div className={styles.error}>{error}</div>}

        <div className={styles.statusRow}>
          <span className={`${styles.statusDot} ${state === "active" ? styles.statusDotActive : ""}`} />
          <span>
            {state === "idle" && "Prêt à démarrer"}
            {state === "connecting" && "Connexion en cours…"}
            {state === "active" && (agentTalking ? "L'agent parle…" : "En écoute…")}
            {state === "ended" && "Appel terminé"}
            {state === "error" && "Erreur"}
          </span>
        </div>

        <div className={styles.actions}>
          {state === "idle" || state === "ended" || state === "error" ? (
            <button className={styles.startButton} onClick={handleStart}>
              {state === "idle" ? "Démarrer le test" : "Relancer"}
            </button>
          ) : (
            <button className={styles.stopButton} onClick={handleStop} disabled={state === "connecting"}>
              Terminer l'appel
            </button>
          )}
        </div>

        {transcript.length > 0 && (
          <div className={styles.transcript}>
            {transcript.map((turn, i) => (
              <div key={i} className={styles.transcriptLine}>
                <strong>{turn.role === "agent" ? "Agent" : "Vous"} : </strong>
                {turn.content}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
