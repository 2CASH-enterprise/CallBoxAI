"use client";

import { useState } from "react";
import { Phone, PhoneCall, X, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import styles from "./DemoCallWidget.module.css";

type CallState = "idle" | "dialing" | "success" | "error";

export function DemoCallWidget() {
  const [open, setOpen] = useState(false);
  const [phone, setPhone] = useState("");
  const [callState, setCallState] = useState<CallState>("idle");
  const [errorMessage, setErrorMessage] = useState("");

  async function handleDemoCall(e: React.FormEvent) {
    e.preventDefault();
    if (!phone.trim()) return;
    setCallState("dialing");
    setErrorMessage("");
    try {
      await api.requestDemoCall(phone.trim());
      setCallState("success");
    } catch (err) {
      setCallState("error");
      setErrorMessage(err instanceof Error ? err.message : "Échec du déclenchement de l'appel.");
    }
  }

  if (!open) {
    return (
      <button className={styles.bubble} onClick={() => setOpen(true)}>
        <span className={styles.bubbleAvatar}>
          <Sparkles size={16} />
        </span>
        <span className={styles.bubbleText}>Testez-moi</span>
      </button>
    );
  }

  return (
    <div className={styles.panel}>
      <div className={styles.panelHeader}>
        <div className={styles.panelHeaderLeft}>
          <span className={`${styles.panelAvatar} ${callState === "dialing" ? styles.ringing : ""}`}>
            <Phone size={15} />
          </span>
          <div>
            <div className={styles.panelTitle}>Testez l'agent CallBoxAI</div>
            <div className={styles.panelSubtitle}>Un vrai appel, en quelques secondes</div>
          </div>
        </div>
        <button className={styles.closeButton} onClick={() => setOpen(false)} aria-label="Fermer">
          <X size={15} />
        </button>
      </div>

      <div className={styles.panelBody}>
        {callState === "idle" || callState === "error" ? (
          <form onSubmit={handleDemoCall}>
            <input
              type="tel"
              required
              placeholder="+33 6 12 34 56 78"
              className={styles.input}
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              autoFocus
            />
            <button type="submit" className={styles.callButton}>
              <PhoneCall size={14} /> Appelez-moi
            </button>
            {callState === "error" && <div className={styles.error}>{errorMessage}</div>}
            <p className={styles.disclaimer}>Un appel de démonstration par numéro et par jour.</p>
          </form>
        ) : callState === "dialing" ? (
          <div className={styles.status}>
            <span className={styles.ringDot} /> Composition vers {phone}…
          </div>
        ) : (
          <div className={styles.status}>
            <PhoneCall size={15} /> Vous allez recevoir un appel dans quelques instants.
          </div>
        )}
      </div>
    </div>
  );
}
