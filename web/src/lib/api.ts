import type {
  Account,
  ChatResponse,
  Opportunity,
  WorkflowResultEnvelope,
  WorkflowStatus,
} from './types';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL;

// Normalize endpoint joins so callers only pass API paths.
function buildUrl(path: string): string {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  return `${getApiBaseUrl()}${normalizedPath}`;
}

// Resolve the local API host from the current browser host when no env var is set.
function getApiBaseUrl(): string {
  if (API_BASE_URL) {
    return API_BASE_URL;
  }
  if (typeof window === 'undefined') {
    return 'http://localhost:8123';
  }
  return `http://${window.location.hostname}:8123`;
}

// Wrap fetch to keep response validation and error copy consistent.
async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(buildUrl(path), {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
  });

  // Surface backend errors with enough context for local debugging.
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed with status ${response.status}`);
  }

  return response.json() as Promise<T>;
}

// Fetch account options from the local FastAPI service.
export function fetchAccounts(): Promise<Account[]> {
  return requestJson<Account[]>('/api/recommendation-context/accounts');
}

// Fetch opportunity options, scoped to the selected account when available.
export function fetchOpportunities(accountId?: string): Promise<Opportunity[]> {
  const query = accountId ? `?account_id=${encodeURIComponent(accountId)}` : '';
  return requestJson<Opportunity[]>(`/api/recommendation-context/opportunities${query}`);
}

// Submit a recommendation request through the chat-shaped backend contract.
export function sendChatMessage(payload: {
  input_text: string;
  chat_id?: string | null;
  account_id?: string | null;
  opportunity_id?: string | null;
}): Promise<ChatResponse> {
  return requestJson<ChatResponse>('/chat/message', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

// Load completed recommendation cards from the workflow result endpoint.
export function fetchWorkflowResult(workflowId: string): Promise<WorkflowResultEnvelope> {
  const query = `?workflow_id=${encodeURIComponent(workflowId)}`;
  return requestJson<WorkflowResultEnvelope>(`/workflow/result${query}`);
}

// Poll the staged workflow status while the backend simulates processing.
export function fetchWorkflowStatus(workflowId: string): Promise<WorkflowStatus> {
  const query = `?workflow_id=${encodeURIComponent(workflowId)}`;
  return requestJson<WorkflowStatus>(`/workflow/status${query}`);
}
