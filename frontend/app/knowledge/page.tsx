"use client";

import { useEffect, useRef, useState } from "react";
import { useOrganization } from "@/lib/OrganizationContext";
import { api, KnowledgeDocument, KnowledgeSearchResult } from "@/lib/api";
import styles from "./knowledge.module.css";

export default function KnowledgePage() {
  const { currentOrg } = useOrganization();
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [loading, setLoading] = useState(true);

  const [modalOpen, setModalOpen] = useState(false);
  const [mode, setMode] = useState<"text" | "file">("text");
  const [form, setForm] = useState({ title: "", content: "" });
  const [submitting, setSubmitting] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [query, setQuery] = useState("");
  const [results, setResults] = useState<KnowledgeSearchResult[] | null>(null);
  const [searching, setSearching] = useState(false);

  const load = () => {
    if (!currentOrg) return;
    setLoading(true);
    api.listKnowledgeDocuments(currentOrg.organization_id).then(setDocuments).finally(() => setLoading(false));
  };

  useEffect(load, [currentOrg]);

  async function handleCreateText(e: React.FormEvent) {
    e.preventDefault();
    if (!currentOrg || !form.title.trim() || !form.content.trim()) return;
    setSubmitting(true);
    try {
      await api.createKnowledgeDocument(currentOrg.organization_id, { title: form.title.trim(), content: form.content });
      setForm({ title: "", content: "" });
      setModalOpen(false);
      load();
    } finally {
      setSubmitting(false);
    }
  }

  async function handleUploadFile(e: React.ChangeEvent<HTMLInputElement>) {
    if (!currentOrg || !e.target.files?.[0]) return;
    setSubmitting(true);
    try {
      await api.uploadKnowledgeDocument(currentOrg.organization_id, e.target.files[0]);
      setModalOpen(false);
      load();
    } finally {
      setSubmitting(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function handleDelete(documentId: string) {
    if (!currentOrg) return;
    await api.deleteKnowledgeDocument(currentOrg.organization_id, documentId);
    load();
  }

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!currentOrg || !query.trim()) return;
    setSearching(true);
    try {
      const res = await api.searchKnowledgeBase(currentOrg.organization_id, query.trim());
      setResults(res);
    } finally {
      setSearching(false);
    }
  }

  if (!currentOrg) {
    return <p style={{ color: "var(--color-muted)" }}>Sélectionnez ou créez une organisation.</p>;
  }

  return (
    <div>
      <div className={styles.header}>
        <h1 className={styles.title}>Base de connaissances</h1>
        <button className={styles.button} onClick={() => setModalOpen(true)}>
          + Ajouter un document
        </button>
      </div>

      <div className={styles.section}>
        <div className={styles.sectionHeader}>Tester la recherche</div>
        <form className={styles.searchBar} onSubmit={handleSearch}>
          <input
            placeholder="Ex : quels sont vos horaires d'ouverture ?"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <button type="submit" disabled={searching}>
            {searching ? "Recherche…" : "Rechercher"}
          </button>
        </form>

        {results && (
          results.length === 0 ? (
            <div className={styles.emptyState}>Aucun résultat — ajoutez d'abord des documents.</div>
          ) : (
            results.map((r) => (
              <div key={r.chunk_id} className={styles.resultCard}>
                <div className={styles.resultHead}>
                  <span className={styles.resultDoc}>{r.document_title}</span>
                  <span className={styles.resultScore}>similarité : {r.score}</span>
                </div>
                <div className={styles.resultContent}>{r.content}</div>
              </div>
            ))
          )
        )}
      </div>

      <div className={styles.section}>
        <div className={styles.sectionHeader}>Documents ({documents.length})</div>
        {loading ? (
          <p style={{ color: "var(--color-muted)" }}>Chargement…</p>
        ) : documents.length === 0 ? (
          <div className={styles.emptyState}>
            Aucun document pour l'instant. Ajoutez votre FAQ, vos tarifs ou vos horaires pour que vos agents puissent les consulter pendant les appels.
          </div>
        ) : (
          documents.map((d) => (
            <div key={d.id} className={styles.row}>
              <span>{d.title}</span>
              <span className={styles.tag}>{d.source_type === "text" ? "Texte collé" : "Fichier .txt"}</span>
              <span style={{ color: "var(--color-muted)" }}>{d.chunks_count} chunk(s)</span>
              <span style={{ color: "var(--color-muted)", fontFamily: "var(--font-mono)", fontSize: 12 }}>
                {new Date(d.created_at).toLocaleDateString("fr-FR")}
              </span>
              <button className={styles.deleteButton} onClick={() => handleDelete(d.id)}>
                Supprimer
              </button>
            </div>
          ))
        )}
      </div>

      {modalOpen && (
        <div className={styles.modalOverlay} onClick={() => setModalOpen(false)}>
          <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
            <h2>Ajouter un document</h2>

            <div className={styles.tabs}>
              <button className={`${styles.tab} ${mode === "text" ? styles.tabActive : ""}`} onClick={() => setMode("text")}>
                Coller du texte
              </button>
              <button className={`${styles.tab} ${mode === "file" ? styles.tabActive : ""}`} onClick={() => setMode("file")}>
                Fichier .txt
              </button>
            </div>

            {mode === "text" ? (
              <form className={styles.form} onSubmit={handleCreateText}>
                <input
                  placeholder="Titre (ex. FAQ, Tarifs, Horaires)"
                  value={form.title}
                  onChange={(e) => setForm({ ...form, title: e.target.value })}
                  required
                />
                <textarea
                  rows={8}
                  placeholder="Collez ici le contenu (FAQ, tarifs, conditions commerciales...)"
                  value={form.content}
                  onChange={(e) => setForm({ ...form, content: e.target.value })}
                  required
                />
                <div className={styles.modalActions}>
                  <button type="button" className={styles.cancelButton} onClick={() => setModalOpen(false)}>
                    Annuler
                  </button>
                  <button type="submit" className={styles.button} disabled={submitting}>
                    {submitting ? "Ajout…" : "Ajouter"}
                  </button>
                </div>
              </form>
            ) : (
              <div className={styles.form}>
                <p style={{ fontSize: 13, color: "var(--color-muted)" }}>
                  Seuls les fichiers .txt sont supportés pour l'instant (extraction PDF/DOCX à venir).
                </p>
                <input ref={fileInputRef} type="file" accept=".txt" onChange={handleUploadFile} disabled={submitting} />
                <div className={styles.modalActions}>
                  <button type="button" className={styles.cancelButton} onClick={() => setModalOpen(false)}>
                    Fermer
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
