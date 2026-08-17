"use client";

/**
 * Contexte "organisation courante" — dérivé des memberships de l'utilisateur
 * connecté (section 24), plus la liste ouverte d'avant l'authentification.
 * Un Super Admin sans membership n'a pas d'organisation "client" à choisir
 * (c'est normal : son rôle porte sur le pilotage, pas sur un client précis).
 */
import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { useAuth } from "./AuthContext";
import { Membership } from "./api";

interface OrgContextValue {
  memberships: Membership[];
  currentOrg: Membership | null;
  loading: boolean;
  selectOrganization: (id: string) => void;
}

const OrgContext = createContext<OrgContextValue | undefined>(undefined);

const STORAGE_KEY = "callboxai:current-org-id";

export function OrganizationProvider({ children }: { children: ReactNode }) {
  const { user, loading: authLoading } = useAuth();
  const [currentOrgId, setCurrentOrgId] = useState<string | null>(null);

  useEffect(() => {
    if (!user) {
      setCurrentOrgId(null);
      return;
    }
    const memberships = user.memberships;
    const stored = typeof window !== "undefined" ? localStorage.getItem(STORAGE_KEY) : null;
    const validStored = stored && memberships.some((m) => m.organization_id === stored) ? stored : null;

    if (validStored) {
      setCurrentOrgId(validStored);
    } else if (memberships.length > 0) {
      setCurrentOrgId(memberships[0].organization_id);
      localStorage.setItem(STORAGE_KEY, memberships[0].organization_id);
    } else {
      setCurrentOrgId(null);
    }
  }, [user]);

  const selectOrganization = (id: string) => {
    setCurrentOrgId(id);
    localStorage.setItem(STORAGE_KEY, id);
  };

  const memberships = user?.memberships || [];
  const currentOrg = memberships.find((m) => m.organization_id === currentOrgId) || null;

  return (
    <OrgContext.Provider value={{ memberships, currentOrg, loading: authLoading, selectOrganization }}>
      {children}
    </OrgContext.Provider>
  );
}

export function useOrganization() {
  const ctx = useContext(OrgContext);
  if (!ctx) throw new Error("useOrganization doit être utilisé dans OrganizationProvider");
  return ctx;
}
