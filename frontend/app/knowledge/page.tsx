"use client";

import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useOrganization } from "@/lib/OrganizationContext";
import { api, KnowledgeDocument, KnowledgeSearchResult, OrganizationSources, Campaign } from "@/lib/api";
import styles from "./knowledge.module.css";

const OBJECTIONS_TEMPLATE = {
  title: "Objections fréquentes",
  content:
    "Objection : \"C'est trop cher\"\n" +
    "Réponse : [expliquez ce qui justifie le prix — ce qui est inclus, le résultat obtenu]\n\n" +
    "Objection : \"J'ai déjà un fournisseur/une solution\"\n" +
    "Réponse : [ce qui différencie votre offre, ce que le client pourrait gagner à changer]\n\n" +
    "Objection : \"Je n'ai pas le temps là\"\n" +
    "Réponse : [proposer un rappel à un horaire précis plutôt que d'insister]\n\n" +
    "Ajoutez ici les objections propres à votre secteur et vos réponses habituelles.",
};

export default function KnowledgePage() {
  const { currentOrg } = useOrganization();
  const searchParams = useSearchParams();
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [connectingFacebook, setConnectingFacebook] = useState(false);

  const [sources, setSources] = useState<OrganizationSources | null>(null);
  const [websiteUrl, setWebsiteUrl] = useState("");
  const [socialMediaUrls, setSocialMediaUrls] = useState("");
  const [facebookPageId, setFacebookPageId] = useState("");
  const [facebookPageAccessToken, setFacebookPageAccessToken] = useState("");
  const [facebookLeadsCampaignId, setFacebookLeadsCampaignId] = useState("");
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [savingSources, setSavingSources] = useState(false);

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
    api.listCampaigns(currentOrg.organization_id).then(setCampaigns);
    api.getOrganizationSources(currentOrg.organization_id).then((s) => {
      setSources(s);
      setWebsiteUrl(s.website_url || "");
      setSocialMediaUrls(s.social_media_urls || "");
      setFacebookPageId(s.facebook_page_id || "");
      setFacebookPageAccessToken(s.facebook_page_access_token || "");
      setFacebookLeadsCampaignId(s.facebook_leads_campaign_id || "");
    });
  };

  useEffect(load, [currentOrg]);

  // Après retour du flux OAuth Facebook (section 42/43) : recharge les
  // sources pour afficher le vrai statut, puis nettoie l'URL pour éviter
  // qu'un rafraîchissement ne redéclenche la même redirection.
  useEffect(() => {
    if (searchParams.get("facebook_connected") || searchParams.get("facebook_error")) {
      load();
      window.history.replaceState({}, "", "/knowledge");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  async function handleConnectFacebook() {
    if (!currentOrg) return;
    setConnectingFacebook(true);
    try {
      const { authorize_url } = await api.getFacebookAuthorizeUrl(currentOrg.organization_id);
      window.location.href = authorize_url;
    } finally {
      setConnectingFacebook(false);
    }
  }

  async function handleSaveSources(e: React.FormEvent) {
    e.preventDefault();
    if (!currentOrg) return;
    setSavingSources(true);
    try {
      const updated = await api.updateOrganizationSources(currentOrg.organization_id, {
        website_url: websiteUrl.trim(),
        social_media_urls: socialMediaUrls.trim(),
        facebook_page_id: facebookPageId.trim(),
        facebook_page_access_token: facebookPageAccessToken.trim(),
        facebook_leads_campaign_id: facebookLeadsCampaignId || undefined,
      });
      setSources(updated);
    } finally {
      setSavingSources(false);
    }
  }

  function useObjectionsTemplate() {
    setForm(OBJECTIONS_TEMPLATE);
    setMode("text");
    setModalOpen(true);
  }

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
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn btn-ghost" onClick={useObjectionsTemplate}>
            + Modèle "Objections fréquentes"
          </button>
          <button className={styles.button} onClick={() => setModalOpen(true)}>
            + Ajouter un document
          </button>
        </div>
      </div>

      <div className={styles.section}>
        <div className={styles.sectionHeader}>Sources de l'entreprise (recommandé)</div>
        <p style={{ fontSize: 13, color: "var(--color-muted)", marginBottom: 12 }}>
          Votre site web et vos réseaux sociaux sont automatiquement explorés et tenus à jour (resynchronisation
          toutes les 24h), pour une meilleure connaissance de votre entreprise — jamais obligatoire.
        </p>
        <form onSubmit={handleSaveSources} className={styles.sourcesForm}>
          <input
            placeholder="Site web (ex. https://mon-entreprise.com)"
            value={websiteUrl}
            onChange={(e) => setWebsiteUrl(e.target.value)}
          />
          <textarea
            rows={2}
            placeholder="Réseaux sociaux — une URL par ligne (Facebook, Instagram, LinkedIn...)"
            value={socialMediaUrls}
            onChange={(e) => setSocialMediaUrls(e.target.value)}
          />
          <button type="submit" className="btn btn-primary" disabled={savingSources}>
            {savingSources ? "Enregistrement…" : "Enregistrer"}
          </button>
        </form>
        {sources && sources.documents_count < 2 && (
          <p style={{ fontSize: 12.5, color: "var(--color-amber)", marginTop: 12 }}>
            {sources.documents_count === 0
              ? "Aucun document pour l'instant — au moins 2 sont recommandés pour de bons résultats."
              : "Un seul document pour l'instant — au moins 2 sont recommandés pour de bons résultats."}
          </p>
        )}
      </div>

      <div className={styles.section}>
        <div className={styles.sectionHeader}>Facebook Lead Ads (prospection B2C)</div>
        <p style={{ fontSize: 13, color: "var(--color-muted)", marginBottom: 12 }}>
          Connectez votre page Facebook en un clic pour que les leads de vos publicités (avec consentement
          explicite au formulaire) soient automatiquement transmis à vos agents commerciaux.
        </p>

        {searchParams.get("facebook_error") && (
          <p style={{ fontSize: 12.5, color: "var(--color-red)", marginBottom: 12 }}>
            La connexion a échoué — réessayez, ou contactez-nous si le problème persiste.
          </p>
        )}

        {sources?.facebook_page_id ? (
          <div>
            <p style={{ fontSize: 13, color: "var(--color-signal)", marginBottom: 8 }}>
              ✓ Page Facebook connectée
              {sources.facebook_subscription_status === "ok" && " — abonnement au webhook confirmé."}
            </p>
            <button className="btn btn-ghost" onClick={handleConnectFacebook} disabled={connectingFacebook}>
              {connectingFacebook ? "Redirection…" : "Reconnecter une autre page"}
            </button>

            <div style={{ marginTop: 16 }}>
              <label style={{ fontSize: 13, display: "block", marginBottom: 6 }}>
                Appeler automatiquement chaque nouveau lead via la campagne :
              </label>
              <select
                value={facebookLeadsCampaignId}
                onChange={async (e) => {
                  setFacebookLeadsCampaignId(e.target.value);
                  if (currentOrg) {
                    const updated = await api.updateOrganizationSources(currentOrg.organization_id, {
                      facebook_leads_campaign_id: e.target.value,
                    });
                    setSources(updated);
                  }
                }}
                style={{
                  border: "1px solid var(--color-line)", borderRadius: "var(--radius-sm)",
                  padding: "8px 10px", fontSize: 13, maxWidth: 360, width: "100%",
                }}
              >
                <option value="">Aucune — capturer sans appeler automatiquement</option>
                {campaigns.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
              <p style={{ fontSize: 12, color: "var(--color-muted)", marginTop: 6 }}>
                Si la campagne n'est pas en cours, le lead est capturé mais l'appel attend qu'elle soit démarrée.
              </p>
            </div>
          </div>
        ) : (
          <button className="btn btn-primary" onClick={handleConnectFacebook} disabled={connectingFacebook}>
            {connectingFacebook ? "Redirection…" : "Connecter ma page Facebook"}
          </button>
        )}

        <details style={{ marginTop: 16 }}>
          <summary style={{ fontSize: 12, color: "var(--color-muted)", cursor: "pointer" }}>
            Configuration manuelle (avancé)
          </summary>
          <form onSubmit={handleSaveSources} className={styles.sourcesForm} style={{ marginTop: 10 }}>
            <input
              placeholder="Identifiant de la page Facebook (Page ID)"
              value={facebookPageId}
              onChange={(e) => setFacebookPageId(e.target.value)}
            />
            <input
              type="password"
              placeholder="Jeton d'accès de la page (Page Access Token)"
              value={facebookPageAccessToken}
              onChange={(e) => setFacebookPageAccessToken(e.target.value)}
            />
            <button type="submit" className="btn btn-ghost" disabled={savingSources}>
              {savingSources ? "Enregistrement…" : "Enregistrer manuellement"}
            </button>
          </form>
          {sources?.facebook_subscription_status === "failed" && (
            <p style={{ fontSize: 12.5, color: "var(--color-red)", marginTop: 12 }}>
              L'abonnement automatique a échoué — vérifiez l'identifiant de page et le jeton d'accès (doit avoir les
              permissions pages_manage_metadata et leads_retrieval).
            </p>
          )}
        </details>
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
