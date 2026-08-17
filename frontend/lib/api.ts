/**
 * Client API minimal vers le backend FastAPI.
 * L'organization_id est transmis en header (voir app/api/routes/agents.py
 * côté backend) — sera remplacé par un vrai JWT lors de l'implémentation
 * de l'authentification (section 24 du cahier des charges).
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(
  path: string,
  options: RequestInit & { organizationId?: string } = {}
): Promise<T> {
  const { organizationId, headers, ...rest } = options;

  const finalHeaders: Record<string, string> = {
    "Content-Type": "application/json",
    ...(headers as Record<string, string>),
  };
  if (organizationId) {
    finalHeaders["x-organization-id"] = organizationId;
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

export const api = {
  listOrganizations: () => request<Organization[]>("/organizations"),
  createOrganization: (name: string, country?: string) =>
    request<Organization>("/organizations", {
      method: "POST",
      body: JSON.stringify({ name, country }),
    }),

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
};
