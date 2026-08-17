"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, Distributor, DistributorClient, DistributorDashboard, Commission } from "@/lib/api";
import { useAuth } from "@/lib/AuthContext";
import { KpiCard } from "@/components/KpiCard";
import styles from "./distributors.module.css";

export default function DistributorsPage() {
  const { user } = useAuth();
  const router = useRouter();
  const isSuperAdmin = !!user?.is_super_admin;
  const ownDistributorId = user?.distributor_id || null;

  const [distributors, setDistributors] = useState<Distributor[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [dashboard, setDashboard] = useState<DistributorDashboard | null>(null);
  const [clients, setClients] = useState<DistributorClient[]>([]);
  const [commissions, setCommissions] = useState<Commission[]>([]);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [calculating, setCalculating] = useState(false);

  const [showNewDistributor, setShowNewDistributor] = useState(false);
  const [newDist, setNewDist] = useState({ name: "", email: "", password: "", country: "", commission_rate: "10" });
  const [showNewClient, setShowNewClient] = useState(false);
  const [newClient, setNewClient] = useState({ name: "", owner_email: "", owner_password: "", owner_full_name: "" });
  const [showBrandingForm, setShowBrandingForm] = useState(false);
  const [branding, setBranding] = useState({ brand_name: "", logo_url: "", primary_color: "" });
  const [savingBranding, setSavingBranding] = useState(false);

  // Garde-fou : cette page est réservée au Super Admin et aux Distributeurs
  // (section 39.4). Le Sidebar cache déjà le lien, ceci protège aussi l'accès
  // direct par URL.
  useEffect(() => {
    if (user && !isSuperAdmin && !ownDistributorId) {
      router.replace("/dashboard");
    }
  }, [user, isSuperAdmin, ownDistributorId, router]);

  const loadDistributors = () => {
    if (isSuperAdmin) {
      // Super Admin : peut parcourir tous les distributeurs.
      api.listDistributors().then((list) => {
        setDistributors(list);
        if (!selectedId && list.length > 0) setSelectedId(list[0].id);
      });
    } else if (ownDistributorId) {
      // Distributeur : accès direct à SON portefeuille uniquement, pas de
      // liste (l'endpoint /distributors est réservé au Super Admin).
      setSelectedId(ownDistributorId);
    }
  };

  useEffect(loadDistributors, [isSuperAdmin, ownDistributorId]);

  const loadDetail = () => {
    if (!selectedId) return;
    setLoadingDetail(true);
    Promise.all([
      api.getDistributorDashboard(selectedId),
      api.listDistributorClients(selectedId),
      api.listCommissions(selectedId),
    ])
      .then(([d, c, com]) => {
        setDashboard(d);
        setClients(c);
        setCommissions(com);
      })
      .finally(() => setLoadingDetail(false));
  };

  useEffect(loadDetail, [selectedId]);

  useEffect(() => {
    if (dashboard) {
      setBranding({
        brand_name: dashboard.distributor.brand_name || "",
        logo_url: dashboard.distributor.logo_url || "",
        primary_color: dashboard.distributor.primary_color || "",
      });
    }
  }, [dashboard?.distributor.id]);

  async function handleCreateDistributor(e: React.FormEvent) {
    e.preventDefault();
    if (!newDist.name.trim() || !newDist.email.trim() || newDist.password.length < 8) return;
    const created = await api.createDistributor({
      name: newDist.name.trim(),
      email: newDist.email.trim(),
      password: newDist.password,
      country: newDist.country.trim() || undefined,
      commission_rate: parseFloat(newDist.commission_rate) || 10,
    });
    setNewDist({ name: "", email: "", password: "", country: "", commission_rate: "10" });
    setShowNewDistributor(false);
    setDistributors((prev) => [...prev, created]);
    setSelectedId(created.id);
  }

  async function handleOnboardClient(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedId || !newClient.name.trim() || !newClient.owner_email.trim() || newClient.owner_password.length < 8) return;
    await api.onboardDistributorClient(selectedId, {
      name: newClient.name.trim(),
      owner_email: newClient.owner_email.trim(),
      owner_password: newClient.owner_password,
      owner_full_name: newClient.owner_full_name.trim() || "Propriétaire",
    });
    setNewClient({ name: "", owner_email: "", owner_password: "", owner_full_name: "" });
    setShowNewClient(false);
    loadDetail();
  }

  async function handleSaveBranding(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedId) return;
    setSavingBranding(true);
    try {
      const updated = await api.updateBranding(selectedId, {
        brand_name: branding.brand_name.trim() || undefined,
        logo_url: branding.logo_url.trim() || undefined,
        primary_color: branding.primary_color.trim() || undefined,
      });
      setDashboard((prev) => (prev ? { ...prev, distributor: updated } : prev));
      setShowBrandingForm(false);
    } finally {
      setSavingBranding(false);
    }
  }

  async function handleCalculate() {
    if (!selectedId) return;
    setCalculating(true);
    try {
      await api.calculateCommissions(selectedId);
      loadDetail();
    } finally {
      setCalculating(false);
    }
  }

  return (
    <div>
      <div className={styles.header}>
        <h1 className={styles.title}>Distributeurs</h1>
      </div>

      <div className={isSuperAdmin ? styles.layout : undefined}>
        {isSuperAdmin && (
        <div className={styles.panel}>
          <div className={styles.panelHeader}>
            <span>Portefeuille</span>
            <button className={styles.addLink} onClick={() => setShowNewDistributor((v) => !v)}>
              + Nouveau
            </button>
          </div>

          {showNewDistributor && (
            <form className={styles.form} onSubmit={handleCreateDistributor}>
              <input
                placeholder="Nom du distributeur"
                value={newDist.name}
                onChange={(e) => setNewDist({ ...newDist, name: e.target.value })}
                required
              />
              <input
                placeholder="Email"
                type="email"
                value={newDist.email}
                onChange={(e) => setNewDist({ ...newDist, email: e.target.value })}
                required
              />
              <input
                placeholder="Mot de passe (8 caractères min.)"
                type="password"
                minLength={8}
                value={newDist.password}
                onChange={(e) => setNewDist({ ...newDist, password: e.target.value })}
                required
              />
              <input
                placeholder="Pays (optionnel)"
                value={newDist.country}
                onChange={(e) => setNewDist({ ...newDist, country: e.target.value })}
              />
              <input
                placeholder="Taux de commission (%)"
                type="number"
                value={newDist.commission_rate}
                onChange={(e) => setNewDist({ ...newDist, commission_rate: e.target.value })}
              />
              <button type="submit">Créer</button>
            </form>
          )}

          {distributors.length === 0 && !showNewDistributor ? (
            <div className={styles.emptyState}>Aucun distributeur pour l'instant.</div>
          ) : (
            distributors.map((d) => (
              <button
                key={d.id}
                className={`${styles.distItem} ${selectedId === d.id ? styles.distItemActive : ""}`}
                onClick={() => setSelectedId(d.id)}
              >
                {d.name}
                <span className={styles.distEmail}>{d.email}</span>
              </button>
            ))
          )}
        </div>
        )}

        <div>
          {!selectedId ? (
            <p style={{ color: "var(--color-muted)" }}>
              Créez ou sélectionnez un distributeur pour voir son portefeuille.
            </p>
          ) : loadingDetail && !dashboard ? (
            <p style={{ color: "var(--color-muted)" }}>Chargement…</p>
          ) : (
            dashboard && (
              <>
                <div className={styles.grid}>
                  <KpiCard label="Clients" value={dashboard.total_clients} />
                  <KpiCard label="Appels (portefeuille)" value={dashboard.total_calls} />
                  <KpiCard
                    label={`Commission (${dashboard.current_period})`}
                    value={`${dashboard.estimated_commission_current_period.toLocaleString("fr-FR")} FCFA`}
                  />
                  <KpiCard label="Taux" value={`${dashboard.distributor.commission_rate}%`} />
                </div>

                <div className={styles.section}>
                  <div className={styles.sectionHeader}>
                    <span>Marque blanche</span>
                    <button className={styles.actionButton} onClick={() => setShowBrandingForm((v) => !v)}>
                      {dashboard.distributor.brand_name ? "Modifier" : "Configurer"}
                    </button>
                  </div>

                  {showBrandingForm ? (
                    <form className={styles.form} onSubmit={handleSaveBranding}>
                      <input
                        placeholder="Nom de marque (ex. Sonatel Business)"
                        value={branding.brand_name}
                        onChange={(e) => setBranding({ ...branding, brand_name: e.target.value })}
                      />
                      <input
                        placeholder="URL du logo (https://...)"
                        value={branding.logo_url}
                        onChange={(e) => setBranding({ ...branding, logo_url: e.target.value })}
                      />
                      <input
                        placeholder="Couleur d'accent (ex. #FF6600)"
                        value={branding.primary_color}
                        onChange={(e) => setBranding({ ...branding, primary_color: e.target.value })}
                      />
                      <button type="submit" disabled={savingBranding}>
                        {savingBranding ? "Enregistrement…" : "Enregistrer la marque"}
                      </button>
                    </form>
                  ) : dashboard.distributor.brand_name ? (
                    <div className={styles.row}>
                      {dashboard.distributor.logo_url && (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img src={dashboard.distributor.logo_url} alt="" style={{ height: 24 }} />
                      )}
                      <span>{dashboard.distributor.brand_name}</span>
                      <span style={{ color: "var(--color-muted)", fontFamily: "var(--font-mono)", fontSize: 12 }}>
                        Visible par ce distributeur et par tous ses clients dès leur connexion.
                      </span>
                    </div>
                  ) : (
                    <div className={styles.emptyState}>
                      Pas encore de marque personnalisée — ce distributeur et ses clients voient la marque par défaut.
                    </div>
                  )}
                </div>

                <div className={styles.section}>
                  <div className={styles.sectionHeader}>
                    <span>Clients du portefeuille</span>
                    <button className={styles.actionButton} onClick={() => setShowNewClient((v) => !v)}>
                      + Nouveau client
                    </button>
                  </div>

                  {showNewClient && (
                    <form className={styles.form} onSubmit={handleOnboardClient}>
                      <input
                        placeholder="Nom de l'entreprise cliente"
                        value={newClient.name}
                        onChange={(e) => setNewClient({ ...newClient, name: e.target.value })}
                        required
                      />
                      <input
                        placeholder="Email du propriétaire (compte de connexion)"
                        type="email"
                        value={newClient.owner_email}
                        onChange={(e) => setNewClient({ ...newClient, owner_email: e.target.value })}
                        required
                      />
                      <input
                        placeholder="Mot de passe (8 caractères min.)"
                        type="password"
                        minLength={8}
                        value={newClient.owner_password}
                        onChange={(e) => setNewClient({ ...newClient, owner_password: e.target.value })}
                        required
                      />
                      <input
                        placeholder="Nom du propriétaire"
                        value={newClient.owner_full_name}
                        onChange={(e) => setNewClient({ ...newClient, owner_full_name: e.target.value })}
                      />
                      <button type="submit">Rattacher ce client</button>
                    </form>
                  )}

                  {clients.length === 0 ? (
                    <div className={styles.emptyState}>Aucun client rattaché pour l'instant.</div>
                  ) : (
                    clients.map((c) => (
                      <div key={c.id} className={styles.row}>
                        <span>{c.name}</span>
                        <span style={{ color: "var(--color-muted)" }}>{c.country || "—"}</span>
                        <span style={{ color: "var(--color-muted)", fontFamily: "var(--font-mono)", fontSize: 12 }}>
                          {new Date(c.created_at).toLocaleDateString("fr-FR")}
                        </span>
                      </div>
                    ))
                  )}
                </div>

                <div className={styles.section}>
                  <div className={styles.sectionHeader}>
                    <span>Commissions</span>
                    <button className={styles.actionButton} onClick={handleCalculate} disabled={calculating}>
                      {calculating ? "Calcul…" : "Calculer le mois en cours"}
                    </button>
                  </div>

                  {commissions.length === 0 ? (
                    <div className={styles.emptyState}>
                      Aucune commission calculée pour l'instant.
                    </div>
                  ) : (
                    commissions.map((c) => (
                      <div key={c.id} className={styles.row}>
                        <span>{c.period}</span>
                        <span className={styles.rateTag}>{c.rate_applied}%</span>
                        <span>{c.commission_amount.toLocaleString("fr-FR")} FCFA</span>
                      </div>
                    ))
                  )}
                </div>
              </>
            )
          )}
        </div>
      </div>
    </div>
  );
}
