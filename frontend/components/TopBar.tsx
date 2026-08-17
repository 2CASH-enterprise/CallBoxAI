"use client";

import { useOrganization } from "@/lib/OrganizationContext";
import { useAuth } from "@/lib/AuthContext";
import { Waveform } from "./Waveform";
import styles from "./TopBar.module.css";

export function TopBar() {
  const { memberships, currentOrg, selectOrganization } = useOrganization();
  const { user, logout } = useAuth();

  return (
    <header className={styles.topbar}>
      <div className={styles.orgSwitch}>
        {memberships.length > 0 ? (
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
        ) : (
          <span className={styles.mockNote}>Aucune organisation client</span>
        )}
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
        <div className={styles.status}>
          <Waveform live />
          En direct
        </div>
        {user && (
          <div className={styles.userMenu}>
            <span className={styles.userName}>
              {user.full_name || user.email}
              {user.is_super_admin && <span className={styles.roleTag}>Super Admin</span>}
              {user.distributor_id && !user.is_super_admin && <span className={styles.roleTag}>Distributeur</span>}
            </span>
            <button className={styles.logoutButton} onClick={logout}>
              Déconnexion
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
