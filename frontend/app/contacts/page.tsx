"use client";

import { useEffect, useRef, useState } from "react";
import { Users, UploadCloud, ClipboardList, Plus } from "lucide-react";
import { useOrganization } from "@/lib/OrganizationContext";
import { api, Contact } from "@/lib/api";
import { SkeletonRow } from "@/components/Skeleton";
import styles from "./contacts.module.css";

const STATUS_ACCENT: Record<string, string> = {
  "Nouveau": styles.statusNouveau,
  "Contacté": styles.statusNeutral,
  "Intéressé": styles.statusSignal,
  "À rappeler": styles.statusAmber,
  "RDV": styles.statusSignal,
  "Pas intéressé": styles.statusRed,
  "Converti": styles.statusViolet,
};

export default function ContactsPage() {
  const { currentOrg } = useOrganization();
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [loading, setLoading] = useState(true);

  const [phone, setPhone] = useState("");
  const [firstName, setFirstName] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const [importOpen, setImportOpen] = useState(false);
  const [importMode, setImportMode] = useState<"paste" | "file">("paste");
  const [pastedList, setPastedList] = useState("");
  const [importing, setImporting] = useState(false);
  const [importSummary, setImportSummary] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

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

  function toCsv(raw: string): string {
    // Si le texte collé n'a pas déjà un en-tête "phone", on le traite comme
    // une simple liste de numéros (un par ligne) pour rester tolérant.
    const trimmed = raw.trim();
    if (/^phone/i.test(trimmed)) return trimmed;
    const lines = trimmed.split("\n").map((l) => l.trim()).filter(Boolean);
    return "phone\n" + lines.join("\n");
  }

  async function handleImportPaste(e: React.FormEvent) {
    e.preventDefault();
    if (!currentOrg || !pastedList.trim()) return;
    setImporting(true);
    setImportSummary(null);
    try {
      const summary = await api.importContactsText(currentOrg.organization_id, toCsv(pastedList));
      setImportSummary(`${summary.imported} contact(s) importé(s), ${summary.skipped_invalid_phone} numéro(s) invalide(s) ignoré(s).`);
      setPastedList("");
      load();
    } finally {
      setImporting(false);
    }
  }

  async function handleImportFile(e: React.ChangeEvent<HTMLInputElement>) {
    if (!currentOrg || !e.target.files?.[0]) return;
    setImporting(true);
    setImportSummary(null);
    try {
      const summary = await api.importContactsUpload(currentOrg.organization_id, e.target.files[0]);
      setImportSummary(`${summary.imported} contact(s) importé(s), ${summary.skipped_invalid_phone} numéro(s) invalide(s) ignoré(s).`);
      load();
    } finally {
      setImporting(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  if (!currentOrg) {
    return <p style={{ color: "var(--color-muted)" }}>Sélectionnez ou créez une organisation.</p>;
  }

  return (
    <div>
      <div className={styles.header}>
        <h1 className={styles.title}>Contacts (CRM)</h1>
        <button className="btn btn-ghost" onClick={() => setImportOpen((v) => !v)}>
          <UploadCloud size={14} /> Importer une liste
        </button>
      </div>

      {importOpen && (
        <div className={styles.importPanel}>
          <div className={styles.tabs}>
            <button className={`${styles.tab} ${importMode === "paste" ? styles.tabActive : ""}`} onClick={() => setImportMode("paste")}>
              <ClipboardList size={13} /> Coller une liste
            </button>
            <button className={`${styles.tab} ${importMode === "file" ? styles.tabActive : ""}`} onClick={() => setImportMode("file")}>
              <UploadCloud size={13} /> Fichier CSV
            </button>
          </div>

          {importMode === "paste" ? (
            <form onSubmit={handleImportPaste} className={styles.pasteForm}>
              <textarea
                rows={6}
                placeholder={"Un numéro par ligne, par ex. :\n+221770000001\n+221770000002\n+221770000003\n\n(ou collez directement depuis Excel/Sheets avec les colonnes phone,first_name,last_name)"}
                value={pastedList}
                onChange={(e) => setPastedList(e.target.value)}
              />
              <button type="submit" className="btn btn-primary" disabled={importing} style={{ alignSelf: "flex-start" }}>
                {importing ? "Import en cours…" : "Importer cette liste"}
              </button>
            </form>
          ) : (
            <div className={styles.pasteForm}>
              <p className={styles.importHint}>
                Colonnes attendues : <code>phone</code> (obligatoire), <code>first_name</code>, <code>last_name</code> (optionnelles).
                Fonctionne aussi avec des milliers de contacts en un seul fichier.
              </p>
              <input ref={fileInputRef} type="file" accept=".csv" onChange={handleImportFile} disabled={importing} />
            </div>
          )}

          {importSummary && <p className={styles.importSummary}>{importSummary}</p>}
        </div>
      )}

      <form className={styles.addBar} onSubmit={handleAdd}>
        <input placeholder="Prénom (optionnel)" value={firstName} onChange={(e) => setFirstName(e.target.value)} />
        <input placeholder="Numéro de téléphone" required value={phone} onChange={(e) => setPhone(e.target.value)} />
        <button type="submit" className="btn btn-primary" disabled={submitting}>
          <Plus size={14} /> {submitting ? "Ajout…" : "Ajouter un contact"}
        </button>
      </form>

      <div className={styles.table}>
        <div className={`${styles.row} ${styles.rowHead}`}>
          <span>Nom</span>
          <span>Téléphone</span>
          <span>Statut</span>
        </div>
        {loading ? (
          <><SkeletonRow columns={3} /><SkeletonRow columns={3} /><SkeletonRow columns={3} /></>
        ) : contacts.length === 0 ? (
          <div className={styles.emptyState}>
            <Users size={26} strokeWidth={1.5} className={styles.emptyIcon} />
            <p>Aucun contact pour l'instant — ajoutez-en un ou importez une liste complète.</p>
          </div>
        ) : (
          contacts.map((c) => (
            <div key={c.id} className={styles.row}>
              <span>{[c.first_name, c.last_name].filter(Boolean).join(" ") || "—"}</span>
              <span className={styles.phone}>{c.phone}</span>
              <span className={`${styles.statusTag} ${STATUS_ACCENT[c.status] || styles.statusNeutral}`}>{c.status}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
