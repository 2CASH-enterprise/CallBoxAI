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

  const isFormData = typeof FormData !== "undefined" && rest.body instanceof FormData;

  const finalHeaders: Record<string, string> = {
    // Pour un FormData (upload de fichier), le navigateur doit fixer lui-même
    // le Content-Type (avec la "boundary" multipart) — ne pas le forcer ici.
    ...(isFormData ? {} : { "Content-Type": "application/json" }),
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

export interface AgentRequest {
  id: string;
  organization_id: string;
  organization_name?: string;
  use_case: string;
  objective: string;
  status: string;
  admin_notes: string | null;
  created_agent_id: string | null;
  created_at: string;
}

export interface Agent {
  id: string;
  organization_id: string;
  name: string;
  objective: string | null;
  language: string;
  system_prompt: string | null;
  transfer_enabled: boolean;
  transfer_number: string | null;
  transfer_instructions: string | null;
  retell_agent_id: string | null;
  voice_id: string | null;
  business_hours_start: string | null;
  business_hours_end: string | null;
  ticketing_enabled: boolean;
  pms_enabled: boolean;
  kyc_enabled: boolean;
  kyc_link_url: string | null;
  category: string;
  source_template: string | null;
  whatsapp_enabled: boolean;
  meeting_booking_enabled: boolean;
}

export interface AdminAgent extends Agent {
  organization_name: string;
}

export interface Ticket {
  id: string;
  organization_id: string;
  agent_id: string;
  call_id: string | null;
  contact_id: string | null;
  subject: string;
  category: string | null;
  priority: string;
  status: string;
  description: string | null;
  resolution_notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface ReservationBrief {
  appointment_id: string;
  contact_name: string;
  contact_phone: string;
  room_type: string | null;
  check_in: string;
  check_out: string | null;
  status: string;
}

export interface MessageBrief {
  message_id: string;
  caller_name: string | null;
  caller_phone: string;
  content: string;
  urgent: boolean;
  created_at: string;
}

export interface TicketBrief {
  ticket_id: string;
  subject: string;
  category: string | null;
  priority: string;
  status: string;
}

export interface TodayDashboard {
  active_categories: string[];
  show_hotel_section: boolean;
  show_telecom_section: boolean;
  arrivals_today: ReservationBrief[];
  departures_today: ReservationBrief[];
  pending_messages: MessageBrief[];
  open_tickets: TicketBrief[];
  overnight_summary: {
    since: string;
    total_calls: number;
    reservations_made: number;
    kyc_links_sent: number;
  };
}

export interface Message {
  id: string;
  organization_id: string;
  agent_id: string;
  call_id: string | null;
  contact_id: string | null;
  caller_phone: string;
  caller_name: string | null;
  content: string;
  urgent: boolean;
  callback_requested: boolean;
  status: string;
  created_at: string;
}

export interface SurveyQuestion {
  id: string;
  text: string;
  type: "choice" | "rating" | "open";
  options?: string[];
}

export interface Survey {
  id: string;
  organization_id: string;
  agent_id: string;
  title: string;
  questions: SurveyQuestion[];
  created_at: string;
}

export interface SurveyQuestionResult {
  question_id: string;
  question_text: string;
  type: string;
  summary: Record<string, any>;
}

export interface SurveyResults {
  survey_id: string;
  total_responses: number;
  results: SurveyQuestionResult[];
}

export interface Call {
  id: string;
  organization_id: string;
  agent_id: string;
  contact_id: string | null;
  direction: string;
  status: string;
  provider: string;
  provider_call_id: string | null;
  transcript: string | null;
  summary: string | null;
  knowledge_context: string | null;
  transferred_to: string | null;
  transferred_at: string | null;
  intent: string | null;
  qualification: string | null;
  sentiment: string | null;
  score: number | null;
  action_taken: string | null;
}

export interface AnalyticsBreakdownItem {
  label: string;
  count: number;
}

export interface AgentPerformance {
  agent_id: string;
  agent_name: string;
  calls_count: number;
  avg_score: number | null;
}

export interface AnalyticsSummary {
  total_calls: number;
  avg_score: number | null;
  qualification_rate: number;
  appointment_rate: number;
  transfer_rate: number;
  by_intent: AnalyticsBreakdownItem[];
  by_qualification: AnalyticsBreakdownItem[];
  by_sentiment: AnalyticsBreakdownItem[];
  by_agent: AgentPerformance[];
}

export interface KnowledgeDocument {
  id: string;
  organization_id: string;
  title: string;
  source_type: string;
  chunks_count: number;
  created_at: string;
}

export interface KnowledgeSearchResult {
  chunk_id: string;
  document_id: string;
  document_title: string;
  content: string;
  score: number;
}

export interface CampaignStats {
  total: number;
  pending: number;
  completed: number;
  no_answer: number;
  failed: number;
}

export interface Campaign {
  id: string;
  organization_id: string;
  agent_id: string;
  name: string;
  status: string;
  schedule_start: string;
  schedule_end: string;
  max_attempts: number;
  max_follow_ups: number;
  created_at: string;
  started_at: string | null;
}

export interface CampaignDetail extends Campaign {
  stats: CampaignStats;
}

export interface ImportSummary {
  imported: number;
  skipped_invalid_phone: number;
  total_targets: number;
}

export interface PipelineStage {
  status: string;
  count: number;
}

export interface Pipeline {
  funnel: PipelineStage[];
  side_buckets: PipelineStage[];
  total_contacts: number;
}

export interface BatchResult {
  processed: number;
  completed: number;
  no_answer: number;
  failed: number;
  follow_up_scheduled: number;
  message: string | null;
}

export interface Contact {
  id: string;
  organization_id: string;
  first_name: string | null;
  last_name: string | null;
  phone: string;
  email: string | null;
  status: string;
}

export interface Appointment {
  id: string;
  organization_id: string;
  contact_id: string;
  agent_id: string | null;
  call_id: string | null;
  scheduled_at: string;
  duration_minutes: number;
  status: string;
  notes: string | null;
  room_type: string | null;
  check_out_at: string | null;
  pms_confirmation_number: string | null;
  created_at: string;
  contact_name: string | null;
  contact_phone: string | null;
  qualification: string | null;
}

export interface AvailabilityOffer {
  room_type: string;
  rate_per_night: number;
  total_price: number;
  rooms_available: number;
  currency: string;
}

export interface SmsLog {
  id: string;
  to_number: string;
  body: string;
  provider: string;
  created_at: string;
}

export interface WhatsAppLog {
  id: string;
  to_number: string;
  body: string;
  provider: string;
  created_at: string;
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

export interface AdminTotals {
  organizations: number;
  organizations_direct: number;
  organizations_via_distributor: number;
  distributors: number;
  agents: number;
  calls_total: number;
  calls_today: number;
  users: number;
}

export interface AdminOrganizationSummary {
  id: string;
  name: string;
  country: string | null;
  distributor_name: string | null;
  agents_count: number;
  calls_count: number;
  created_at: string;
}

export interface AdminDistributorSummary {
  id: string;
  name: string;
  commission_rate: number;
  clients_count: number;
  calls_count: number;
}

export interface AdminDashboard {
  totals: AdminTotals;
  current_period: string;
  estimated_revenue_current_period: number;
  estimated_commissions_current_period: number;
  organizations: AdminOrganizationSummary[];
  distributors: AdminDistributorSummary[];
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
  requestDemoCall: (phoneNumber: string) =>
    request<{ success: boolean; message: string }>("/public/demo-call", {
      method: "POST",
      skipAuth: true,
      body: JSON.stringify({ phone_number: phoneNumber }),
    }),
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

  createAgentRequest: (organizationId: string, data: { use_case: string; objective: string }) =>
    request<AgentRequest>("/agent-requests", {
      method: "POST",
      organizationId,
      body: JSON.stringify(data),
    }),
  listAgentRequests: (organizationId: string) =>
    request<AgentRequest[]>("/agent-requests", { organizationId }),

  listAllAgentRequests: (status?: string) =>
    request<AgentRequest[]>(`/admin/agent-requests${status ? `?status=${status}` : ""}`),
  updateAgentRequestStatus: (requestId: string, data: { status: string; admin_notes?: string }) =>
    request<AgentRequest>(`/admin/agent-requests/${requestId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  fulfillAgentRequest: (
    requestId: string,
    data: {
      name: string; objective?: string; language?: string; system_prompt?: string;
      transfer_enabled?: boolean; transfer_number?: string; transfer_instructions?: string;
      voice_id?: string; business_hours_start?: string; business_hours_end?: string;
      ticketing_enabled?: boolean; pms_enabled?: boolean; kyc_enabled?: boolean; kyc_link_url?: string;
      whatsapp_enabled?: boolean; meeting_booking_enabled?: boolean;
      category?: string;
    }
  ) =>
    request<AgentRequest>(`/admin/agent-requests/${requestId}/fulfill`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  listAllAgents: () => request<AdminAgent[]>("/admin/agents"),
  adminUpdateAgent: (
    agentId: string,
    data: Partial<{
      name: string; objective: string; language: string; system_prompt: string;
      transfer_enabled: boolean; transfer_number: string; transfer_instructions: string;
      voice_id: string; business_hours_start: string; business_hours_end: string;
      ticketing_enabled: boolean; pms_enabled: boolean; kyc_enabled: boolean; kyc_link_url: string;
      whatsapp_enabled: boolean; meeting_booking_enabled: boolean;
      category: string;
    }>
  ) =>
    request<AdminAgent>(`/admin/agents/${agentId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  createAgent: (
    organizationId: string,
    data: {
      name: string;
      objective?: string;
      system_prompt?: string;
      language?: string;
      transfer_enabled?: boolean;
      transfer_number?: string;
      transfer_instructions?: string;
      voice_id?: string;
      business_hours_start?: string;
      business_hours_end?: string;
      ticketing_enabled?: boolean;
      pms_enabled?: boolean;
      kyc_enabled?: boolean;
      kyc_link_url?: string;
      category?: string;
    }
  ) =>
    request<Agent>("/agents", {
      method: "POST",
      organizationId,
      body: JSON.stringify(data),
    }),
  updateAgent: (
    organizationId: string,
    agentId: string,
    data: Partial<{
      name: string;
      objective: string;
      system_prompt: string;
      language: string;
      transfer_enabled: boolean;
      transfer_number: string;
      transfer_instructions: string;
      voice_id: string;
      business_hours_start: string;
      business_hours_end: string;
      ticketing_enabled: boolean;
      pms_enabled: boolean;
      kyc_enabled: boolean;
      kyc_link_url: string;
      category: string;
    }>
  ) =>
    request<Agent>(`/agents/${agentId}`, {
      method: "PATCH",
      organizationId,
      body: JSON.stringify(data),
    }),
  createAgentTestCall: (organizationId: string, agentId: string) =>
    request<{ access_token: string; call_id: string }>(`/agents/${agentId}/test-call`, {
      method: "POST",
      organizationId,
    }),

  listCalls: (organizationId: string) =>
    request<Call[]>("/calls", { organizationId }),
  createCall: (
    organizationId: string,
    data: { agent_id: string; to_number: string; from_number: string; direction?: string; contact_id?: string }
  ) =>
    request<Call>("/calls", {
      method: "POST",
      organizationId,
      body: JSON.stringify(data),
    }),
  createRealCall: (
    organizationId: string,
    data: { agent_id: string; to_number: string; from_number: string; direction?: string }
  ) =>
    request<Call>("/calls/real", {
      method: "POST",
      organizationId,
      body: JSON.stringify(data),
    }),
  transferCall: (organizationId: string, callId: string, destination?: string) =>
    request<Call>(`/calls/${callId}/transfer`, {
      method: "POST",
      organizationId,
      body: JSON.stringify({ destination }),
    }),

  getAnalyticsSummary: (organizationId: string) =>
    request<AnalyticsSummary>("/analytics/summary", { organizationId }),

  listCampaigns: (organizationId: string) =>
    request<Campaign[]>("/campaigns", { organizationId }),
  createCampaign: (
    organizationId: string,
    data: { name: string; agent_id: string; schedule_start: string; schedule_end: string; max_attempts: number; max_follow_ups: number }
  ) =>
    request<Campaign>("/campaigns", {
      method: "POST",
      organizationId,
      body: JSON.stringify(data),
    }),
  getCampaign: (organizationId: string, campaignId: string) =>
    request<CampaignDetail>(`/campaigns/${campaignId}`, { organizationId }),
  importCampaignContacts: (organizationId: string, campaignId: string, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return request<ImportSummary>(`/campaigns/${campaignId}/import`, {
      method: "POST",
      organizationId,
      body: formData,
    });
  },
  startCampaign: (organizationId: string, campaignId: string) =>
    request<Campaign>(`/campaigns/${campaignId}/start`, { method: "POST", organizationId }),
  pauseCampaign: (organizationId: string, campaignId: string) =>
    request<Campaign>(`/campaigns/${campaignId}/pause`, { method: "POST", organizationId }),
  runCampaignBatch: (organizationId: string, campaignId: string) =>
    request<BatchResult>(`/campaigns/${campaignId}/run-batch`, { method: "POST", organizationId }),

  listKnowledgeDocuments: (organizationId: string) =>
    request<KnowledgeDocument[]>("/knowledge/documents", { organizationId }),
  createKnowledgeDocument: (organizationId: string, data: { title: string; content: string }) =>
    request<KnowledgeDocument>("/knowledge/documents", {
      method: "POST",
      organizationId,
      body: JSON.stringify(data),
    }),
  uploadKnowledgeDocument: (organizationId: string, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return request<KnowledgeDocument>("/knowledge/documents/upload", {
      method: "POST",
      organizationId,
      body: formData,
    });
  },
  deleteKnowledgeDocument: (organizationId: string, documentId: string) =>
    request<void>(`/knowledge/documents/${documentId}`, { method: "DELETE", organizationId }),
  searchKnowledgeBase: (organizationId: string, query: string, top_k = 3) =>
    request<KnowledgeSearchResult[]>("/knowledge/search", {
      method: "POST",
      organizationId,
      body: JSON.stringify({ query, top_k }),
    }),

  listContacts: (organizationId: string) =>
    request<Contact[]>("/contacts", { organizationId }),
  createContact: (
    organizationId: string,
    data: { first_name?: string; last_name?: string; phone: string; email?: string; status?: string }
  ) =>
    request<Contact>("/contacts", {
      method: "POST",
      organizationId,
      body: JSON.stringify(data),
    }),
  importContactsUpload: (organizationId: string, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return request<ImportSummary>("/contacts/import/upload", {
      method: "POST",
      organizationId,
      body: formData,
    });
  },
  importContactsText: (organizationId: string, content: string) =>
    request<ImportSummary>("/contacts/import/text", {
      method: "POST",
      organizationId,
      body: JSON.stringify({ content }),
    }),
  getPipeline: (organizationId: string) =>
    request<Pipeline>("/contacts/pipeline", { organizationId }),

  listMessages: (organizationId: string) =>
    request<Message[]>("/messages", { organizationId }),
  updateMessage: (organizationId: string, messageId: string, status: string) =>
    request<Message>(`/messages/${messageId}`, {
      method: "PATCH",
      organizationId,
      body: JSON.stringify({ status }),
    }),

  listTickets: (organizationId: string) =>
    request<Ticket[]>("/tickets", { organizationId }),
  updateTicket: (
    organizationId: string,
    ticketId: string,
    data: Partial<{ status: string; priority: string; resolution_notes: string }>
  ) =>
    request<Ticket>(`/tickets/${ticketId}`, {
      method: "PATCH",
      organizationId,
      body: JSON.stringify(data),
    }),

  listSurveys: (organizationId: string) =>
    request<Survey[]>("/surveys", { organizationId }),
  createSurvey: (organizationId: string, data: { title: string; agent_id: string; questions: SurveyQuestion[] }) =>
    request<Survey>("/surveys", {
      method: "POST",
      organizationId,
      body: JSON.stringify(data),
    }),
  getSurvey: (organizationId: string, surveyId: string) =>
    request<Survey>(`/surveys/${surveyId}`, { organizationId }),
  callForSurvey: (organizationId: string, surveyId: string, data: { contact_id: string; to_number: string }) =>
    request<{ id: string; answers: Record<string, any> }>(`/surveys/${surveyId}/call`, {
      method: "POST",
      organizationId,
      body: JSON.stringify(data),
    }),
  getSurveyResults: (organizationId: string, surveyId: string) =>
    request<SurveyResults>(`/surveys/${surveyId}/results`, { organizationId }),

  exportContacts: async (organizationId: string, status?: string) => {
    const token = getStoredToken();
    const query = status ? `?status=${encodeURIComponent(status)}` : "";
    const response = await fetch(`${API_URL}/contacts/export${query}`, {
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        "x-organization-id": organizationId,
      },
    });
    if (!response.ok) throw new ApiError(await response.text(), response.status);
    const blob = await response.blob();
    const disposition = response.headers.get("Content-Disposition") || "";
    const match = disposition.match(/filename="(.+)"/);
    const filename = match ? match[1] : "leads.csv";

    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  },

  listAppointments: (organizationId: string) =>
    request<Appointment[]>("/appointments", { organizationId }),
  createAppointment: (
    organizationId: string,
    data: { contact_id: string; scheduled_at: string; duration_minutes?: number; notes?: string }
  ) =>
    request<Appointment>("/appointments", {
      method: "POST",
      organizationId,
      body: JSON.stringify(data),
    }),
  updateAppointment: (
    organizationId: string,
    appointmentId: string,
    data: { status?: string; scheduled_at?: string; notes?: string }
  ) =>
    request<Appointment>(`/appointments/${appointmentId}`, {
      method: "PATCH",
      organizationId,
      body: JSON.stringify(data),
    }),

  checkPmsAvailability: (organizationId: string, data: { check_in: string; check_out: string; room_type?: string }) =>
    request<AvailabilityOffer[]>("/pms/availability", {
      method: "POST",
      organizationId,
      body: JSON.stringify(data),
    }),
  createPmsReservation: (
    organizationId: string,
    data: { contact_id: string; check_in: string; check_out: string; room_type: string; num_guests?: number; guest_email?: string }
  ) =>
    request<{
      id: string;
      pms_confirmation_number: string;
      confirmation_email_sent: boolean;
      confirmation_sms_sent: boolean;
    }>("/pms/reservations", {
      method: "POST",
      organizationId,
      body: JSON.stringify(data),
    }),

  listSms: (organizationId: string) => request<SmsLog[]>("/sms", { organizationId }),
  listWhatsApp: (organizationId: string) => request<WhatsAppLog[]>("/whatsapp", { organizationId }),
  getTodayDashboard: (organizationId: string) => request<TodayDashboard>("/dashboard/today", { organizationId }),

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
  getAdminDashboard: () => request<AdminDashboard>("/admin/dashboard"),

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
