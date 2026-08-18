"use client";

import { useEffect, useState } from "react";
import { ChevronDown, LogOut, ShieldCheck, Network } from "lucide-react";
import { useOrganization } from "@/lib/OrganizationContext";
import { useAuth } from "@/lib/AuthContext";
import { api, Call } from "@/lib/api";
import { Waveform } from "./Waveform";
import styles from "./TopBar.module.css";

export function TopBar() {
  const { memberships, currentOrg, selectOrganization } = useOrganization();
  const { user, logout } = useAuth();
  const [calls, setCalls] = useState<Call[] | null>(null);

  useEffect(() => {
    if (!currentOrg) {
      setCalls(null);
      return;
    }
    api.listCalls(currentOrg.organization_id).then(setCalls).catch(() => setCalls(null));
  }, [currentOrg]);

  const activeCalls = calls?.filter((c) => c.status === "in_progress").length ?? 0;
  const todayCount = calls?.length ?? 0;

  return (
    <header className={styles.topbar}>
      <div className={styles.orgSwitch}>
        {memberships.length > 0 ? (
          <div className={styles.selectWrap}>
            <select
              className={styles.select}
              value={currentOrg?.organization_id || ""}
              onChange={(e) => selectOrganization(e.target.value)}
              aria-label="Organisation active"
            >
              {memberships.map((m) => (
                <option key={m.organization_id} value={m.organization_id}>
                  {m.organization_name}
                </option>
              ))}
            </select>
            <ChevronDown size={14} className={styles.selectChevron} />
          </div>
        ) : (
          <span className={styles.mockNote}>Aucune organisation client</span>
        )}
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
        {currentOrg && (
          <div className={styles.status}>
            <Waveform live={activeCalls > 0} />
            {activeCalls > 0 ? (
              <span>
                <strong>{activeCalls}</strong> appel{activeCalls > 1 ? "s" : ""} en direct
              </span>
            ) : (
              <span>{todayCount} appel{todayCount !== 1 ? "s" : ""} au total</span>
            )}
          </div>
        )}
        {user && (
          <div className={styles.userMenu}>
            <span className={styles.userName}>
              {user.full_name || user.email}
              {user.is_super_admin && (
                <span className={styles.roleTag}>
                  <ShieldCheck size={11} /> Super Admin
                </span>
              )}
              {user.distributor_id && !user.is_super_admin && (
                <span className={styles.roleTagViolet}>
                  <Network size={11} /> Distributeur
                </span>
              )}
            </span>
            <button className={styles.logoutButton} onClick={logout}>
              <LogOut size={13} />
              Déconnexion
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
