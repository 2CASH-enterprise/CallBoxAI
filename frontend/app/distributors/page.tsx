"use client";

import { useEffect, useState } from "react";
import { api, Distributor, DistributorClient, DistributorDashboard, Commission } from "@/lib/api";
import { KpiCard } from "@/components/KpiCard";
import styles from "./distributors.module.css";

export default function DistributorsPage() {
  const [distributors, setDistributors] = useState<Distributor[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [dashboard, setDashboard] = useState<DistributorDashboard | null>(null);
  const [clients, setClients] = useState<DistributorClient[]>([]);
  const [commissions, setCommissions] = useState<Commission[]>([]);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [calculating, setCalculating] = useState(false);

  const [showNewDistributor, setShowNewDistributor] = useState(false);
  const [newDist, setNewDist] = useState({ name: "", email: "", country: "", commission_rate: "10" });
  const [showNewClient, setShowNewClient] = useState(false);
  const [newClientName, setNewClientName] = useState("");

  const loadDistributors = () => {
    api.listDistributors().then((list) => {
      setDistributors(list);
      if (!selectedId && list.length > 0) setSelectedId(list[0].id);
    });
  };

  useEffect(loadDistributors, []);

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

  async function handleCreateDistributor(e: React.FormEvent) {
    e.preventDefault();
    if (!newDist.name.trim() || !newDist.email.trim()) return;
    const created = await api.createDistributor({
      name: newDist.name.trim(),
      email: newDist.email.trim(),
      country: newDist.country.trim() || undefined,
      commission_rate: parseFloat(newDist.commission_rate) || 10,
    });
    setNewDist({ name: "", email: "", country: "", commission_rate: "10" });
    setShowNewDistributor(false);
    setDistributors((prev) => [...prev, created]);
    setSelectedId(created.id);
  }

  async function handleOnboardClient(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedId || !newClientName.trim()) return;
    await api.onboardDistributorClient(selectedId, { name: newClientName.trim() });
    setNewClientName("");
    setShowNewClient(false);
    loadDetail();
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

      <div className={styles.layout}>
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
                    <span>Clients du portefeuille</span>
                    <button className={styles.actionButton} onClick={() => setShowNewClient((v) => !v)}>
                      + Nouveau client
                    </button>
                  </div>

                  {showNewClient && (
                    <form className={styles.form} onSubmit={handleOnboardClient}>
                      <input
                        placeholder="Nom de l'entreprise cliente"
                        value={newClientName}
                        onChange={(e) => setNewClientName(e.target.value)}
                        required
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
