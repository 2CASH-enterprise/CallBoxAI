"use client";

import { useState } from "react";
import { useOrganization } from "@/lib/OrganizationContext";
import { Waveform } from "./Waveform";
import styles from "./TopBar.module.css";

export function TopBar() {
  const { organizations, currentOrg, selectOrganization, createOrganization } = useOrganization();
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!newName.trim()) return;
    setSubmitting(true);
    try {
      await createOrganization(newName.trim());
      setNewName("");
      setCreating(false);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <header className={styles.topbar}>
      <div className={styles.orgSwitch}>
        {!creating ? (
          <>
            <select
              className={styles.select}
              value={currentOrg?.id || ""}
              onChange={(e) => selectOrganization(e.target.value)}
              aria-label="Organisation active"
            >
              {organizations.length === 0 && <option value="">Aucune organisation</option>}
              {organizations.map((org) => (
                <option key={org.id} value={org.id}>
                  {org.name}
                </option>
              ))}
            </select>
            <button className={styles.newOrgButton} onClick={() => setCreating(true)}>
              + Nouvelle organisation
            </button>
          </>
        ) : (
          <form className={styles.newOrgForm} onSubmit={handleCreate}>
            <input
              autoFocus
              placeholder="Nom de l'entreprise"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
            />
            <button type="submit" disabled={submitting}>
              {submitting ? "Création…" : "Créer"}
            </button>
            <button type="button" onClick={() => setCreating(false)} style={{ background: "transparent", color: "var(--color-muted)" }}>
              Annuler
            </button>
          </form>
        )}
      </div>

      <div className={styles.status}>
        <Waveform live />
        En direct
      </div>
    </header>
  );
}
