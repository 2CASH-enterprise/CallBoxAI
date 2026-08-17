"use client";

/**
 * Contexte "organisation courante" — en attendant l'authentification réelle
 * (section 24), l'utilisateur choisit/crée son organisation ici et son id
 * est conservé dans le localStorage du navigateur.
 */
import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { api, Organization } from "./api";

interface OrgContextValue {
  organizations: Organization[];
  currentOrg: Organization | null;
  loading: boolean;
  error: string | null;
  selectOrganization: (id: string) => void;
  createOrganization: (name: string, country?: string) => Promise<void>;
  refresh: () => Promise<void>;
}

const OrgContext = createContext<OrgContextValue | undefined>(undefined);

const STORAGE_KEY = "callboxai:current-org-id";

export function OrganizationProvider({ children }: { children: ReactNode }) {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [currentOrgId, setCurrentOrgId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = async () => {
    setLoading(true);
    setError(null);
    try {
      const orgs = await api.listOrganizations();
      setOrganizations(orgs);

      const stored = typeof window !== "undefined" ? localStorage.getItem(STORAGE_KEY) : null;
      const validStored = stored && orgs.some((o) => o.id === stored) ? stored : null;

      if (validStored) {
        setCurrentOrgId(validStored);
      } else if (orgs.length > 0) {
        setCurrentOrgId(orgs[0].id);
        localStorage.setItem(STORAGE_KEY, orgs[0].id);
      } else {
        setCurrentOrgId(null);
      }
    } catch (e) {
      setError(
        "Impossible de joindre le serveur. Vérifiez que le backend tourne bien (NEXT_PUBLIC_API_URL)."
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const selectOrganization = (id: string) => {
    setCurrentOrgId(id);
    localStorage.setItem(STORAGE_KEY, id);
  };

  const createOrganization = async (name: string, country?: string) => {
    const org = await api.createOrganization(name, country);
    setOrganizations((prev) => [...prev, org]);
    selectOrganization(org.id);
  };

  const currentOrg = organizations.find((o) => o.id === currentOrgId) || null;

  return (
    <OrgContext.Provider
      value={{ organizations, currentOrg, loading, error, selectOrganization, createOrganization, refresh }}
    >
      {children}
    </OrgContext.Provider>
  );
}

export function useOrganization() {
  const ctx = useContext(OrgContext);
  if (!ctx) throw new Error("useOrganization doit être utilisé dans OrganizationProvider");
  return ctx;
}
