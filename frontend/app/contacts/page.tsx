"use client";

import { useEffect, useState } from "react";
import { useOrganization } from "@/lib/OrganizationContext";
import { api, Contact } from "@/lib/api";
import styles from "./contacts.module.css";

export default function ContactsPage() {
  const { currentOrg } = useOrganization();
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [loading, setLoading] = useState(true);
  const [phone, setPhone] = useState("");
  const [firstName, setFirstName] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const load = () => {
    if (!currentOrg) return;
    setLoading(true);
    api.listContacts(currentOrg.organization_id).then(setContacts).finally(() => setLoading(false));
  };

  useEffect(load, [currentOrg]);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!currentOrg || !phone.trim()) return;
    setSubmitting(true);
    try {
      await api.createContact(currentOrg.organization_id, { phone: phone.trim(), first_name: firstName.trim() || undefined });
      setPhone("");
      setFirstName("");
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
        <h1 className={styles.title}>Contacts (CRM)</h1>
      </div>

      <form className={styles.addBar} onSubmit={handleAdd}>
        <input placeholder="Prénom (optionnel)" value={firstName} onChange={(e) => setFirstName(e.target.value)} />
        <input placeholder="Numéro de téléphone" required value={phone} onChange={(e) => setPhone(e.target.value)} />
        <button type="submit" disabled={submitting}>
          {submitting ? "Ajout…" : "Ajouter un contact"}
        </button>
      </form>

      <div className={styles.table}>
        <div className={`${styles.row} ${styles.rowHead}`}>
          <span>Nom</span>
          <span>Téléphone</span>
          <span>Statut</span>
        </div>
        {loading ? (
          <div className={styles.emptyState}>Chargement…</div>
        ) : contacts.length === 0 ? (
          <div className={styles.emptyState}>Aucun contact pour l'instant.</div>
        ) : (
          contacts.map((c) => (
            <div key={c.id} className={styles.row}>
              <span>{[c.first_name, c.last_name].filter(Boolean).join(" ") || "—"}</span>
              <span>{c.phone}</span>
              <span className={styles.statusTag}>{c.status}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
