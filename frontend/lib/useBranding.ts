"use client";

/**
 * Résout la marque à afficher (section 39 : marque blanche distributeur) :
 * - Dans l'espace de pilotage (Distributeur/Super Admin connecté sans
 *   organisation cliente active) : la propre marque du distributeur, si définie.
 * - Dans le Dashboard client : la marque du distributeur de CETTE organisation,
 *   si son distributeur en a défini une.
 * - Sinon (client direct, ou distributeur sans marque personnalisée définie) :
 *   la marque par défaut "CallBoxAI".
 */
import { usePathname } from "next/navigation";
import { useAuth } from "./AuthContext";
import { useOrganization } from "./OrganizationContext";
import { Branding } from "./api";

const DEFAULT_BRANDING = {
  name: "CallBoxAI",
  logoUrl: null as string | null,
  primaryColor: "#12B886",
};

export function useBranding() {
  const { user } = useAuth();
  const { currentOrg } = useOrganization();
  const pathname = usePathname();

  const inPilotageArea = pathname?.startsWith("/distributors");

  let branding: Branding | null = null;
  if (inPilotageArea && user?.distributor_branding) {
    branding = user.distributor_branding;
  } else if (currentOrg?.branding) {
    branding = currentOrg.branding;
  }

  if (!branding) return DEFAULT_BRANDING;

  return {
    name: branding.brand_name || DEFAULT_BRANDING.name,
    logoUrl: branding.logo_url,
    primaryColor: branding.primary_color || DEFAULT_BRANDING.primaryColor,
  };
}
