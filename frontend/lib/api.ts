/**
 * Client API minimal vers le backend FastAPI.
 * Le token JWT (section 24 du cahier des charges) est lu depuis le
 * localStorage et attaché automatiquement à chaque requête protégée.
 * x-organization-id sélectionne QUELLE organisation du user est visée ; le
 * backend vérifie toujours que le user y a vraiment accès.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const TOKEN_STORAGE_KEY = "callboxai:access-token";

export function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_STORAGE_KEY);
}

export function setStoredToken(token: string) {
  localStorage.setItem(TOKEN_STORAGE_KEY, token);
}

export function clearStoredToken() {
  localStorage.removeItem(TOKEN_STORAGE_KEY);
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(
  path: string,
  options: RequestInit & { organizationId?: string; skipAuth?: boolean } = {}
): Promise<T> {
  const { organizationId, skipAuth, headers, ...rest } = options;

  const finalHeaders: Record<string, string> = {
    "Content-Type": "application/json",
    ...(headers as Record<string, string>),
  };
  if (organizationId) {
    finalHeaders["x-organization-id"] = organizationId;
  }
  if (!skipAuth) {
    const token = getStoredToken();
    if (token) {
      finalHeaders["Authorization"] = `Bearer ${token}`;
    }
  }

  const response = await fetch(`${API_URL}${path}`, {
    ...rest,
    headers: finalHeaders,
    cache: "no-store",
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new ApiError(detail || `Erreur ${response.status}`, response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return response.json();
}

export interface Organization {
  id: string;
  name: string;
  country: string | null;
}

export interface Agent {
  id: string;
  organization_id: string;
  name: string;
  objective: string | null;
  language: string;
}

export interface Call {
  id: string;
  organization_id: string;
  agent_id: string;
  direction: string;
  status: string;
  provider: string;
  provider_call_id: string | null;
  transcript: string | null;
  summary: string | null;
}

export interface Contact {
  id: string;
  organization_id: string;
  first_name: string | null;
  last_name: string | null;
  phone: string;
  status: string;
}

export interface Distributor {
  id: string;
  name: string;
  email: string;
  country: string | null;
  commission_rate: number;
  status: string;
  brand_name: string | null;
  logo_url: string | null;
  primary_color: string | null;
}

export interface DistributorClient {
  id: string;
  name: string;
  country: string | null;
  created_at: string;
}

export interface DistributorDashboard {
  distributor: Distributor;
  total_clients: number;
  total_calls: number;
  current_period: string;
  estimated_commission_current_period: number;
}

export interface Commission {
  id: string;
  organization_id: string;
  period: string;
  base_amount: number;
  rate_applied: number;
  commission_amount: number;
  status: string;
}

export interface Branding {
  brand_name: string | null;
  logo_url: string | null;
  primary_color: string | null;
}

export interface Membership {
  organization_id: string;
  organization_name: string;
  role: string;
  branding: Branding | null;
}

export interface Me {
  id: string;
  email: string;
  full_name: string | null;
  is_super_admin: boolean;
  distributor_id: string | null;
  distributor_branding: Branding | null;
  memberships: Membership[];
}

export const api = {
  register: (data: { email: string; password: string; full_name: string; organization_name: string; organization_country?: string }) =>
    request<{ access_token: string }>("/auth/register", {
      method: "POST",
      skipAuth: true,
      body: JSON.stringify(data),
    }),
  login: (email: string, password: string) =>
    request<{ access_token: string }>("/auth/login", {
      method: "POST",
      skipAuth: true,
      body: JSON.stringify({ email, password }),
    }),
  me: () => request<Me>("/auth/me"),

  listAgents: (organizationId: string) =>
    request<Agent[]>("/agents", { organizationId }),
  createAgent: (
    organizationId: string,
    data: { name: string; objective?: string; system_prompt?: string; language?: string }
  ) =>
    request<Agent>("/agents", {
      method: "POST",
      organizationId,
      body: JSON.stringify(data),
    }),

  listCalls: (organizationId: string) =>
    request<Call[]>("/calls", { organizationId }),
  createCall: (
    organizationId: string,
    data: { agent_id: string; to_number: string; from_number: string; direction?: string }
  ) =>
    request<Call>("/calls", {
      method: "POST",
      organizationId,
      body: JSON.stringify(data),
    }),

  listContacts: (organizationId: string) =>
    request<Contact[]>("/contacts", { organizationId }),
  createContact: (
    organizationId: string,
    data: { first_name?: string; last_name?: string; phone: string; status?: string }
  ) =>
    request<Contact>("/contacts", {
      method: "POST",
      organizationId,
      body: JSON.stringify(data),
    }),

  listDistributors: () => request<Distributor[]>("/distributors"),
  createDistributor: (data: { name: string; email: string; password: string; country?: string; commission_rate?: number }) =>
    request<Distributor>("/distributors", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  updateCommissionRate: (distributorId: string, commission_rate: number) =>
    request<Distributor>(`/distributors/${distributorId}/commission-rate`, {
      method: "PATCH",
      body: JSON.stringify({ commission_rate }),
    }),
  updateBranding: (distributorId: string, data: { brand_name?: string; logo_url?: string; primary_color?: string }) =>
    request<Distributor>(`/distributors/${distributorId}/branding`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  getDistributorDashboard: (distributorId: string) =>
    request<DistributorDashboard>(`/distributors/${distributorId}/dashboard`),
  listDistributorClients: (distributorId: string) =>
    request<DistributorClient[]>(`/distributors/${distributorId}/clients`),
  onboardDistributorClient: (
    distributorId: string,
    data: { name: string; country?: string; owner_email: string; owner_password: string; owner_full_name: string }
  ) =>
    request<DistributorClient>(`/distributors/${distributorId}/clients`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  listCommissions: (distributorId: string) =>
    request<Commission[]>(`/distributors/${distributorId}/commissions`),
  calculateCommissions: (distributorId: string) =>
    request<Commission[]>(`/distributors/${distributorId}/commissions/calculate`, {
      method: "POST",
    }),
};
