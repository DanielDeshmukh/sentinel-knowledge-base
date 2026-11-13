import axios from 'axios';
import type {
  User,
  TokenResponse,
  Document,
  ChatRequest,
  ChatResponse,
  CorpusJobSnapshot,
  CorpusMetadata,
  CorpusProgressEvent,
  RoleUpdate,
} from '../types';
import { decodeSseFrame } from './sse';

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Attach token to all requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Auth
export const register = async (displayName: string, email: string, password: string, requestedRole: 'public' | 'internal' | 'restricted') => {
  const response = await api.post<TokenResponse>('/auth/register', {
    display_name: displayName,
    email,
    password,
    requested_role: requestedRole,
  });
  if (response.data.access_token) {
    localStorage.setItem('token', response.data.access_token);
  }
  return response.data;
};

export const login = async (email: string, password: string) => {
  const response = await api.post<TokenResponse>('/auth/login', { email, password });
  if (response.data.access_token) {
    localStorage.setItem('token', response.data.access_token);
  }
  return response.data;
};

export const logout = () => {
  localStorage.removeItem('token');
};

export const getMe = async () => {
  const response = await api.get<User>('/auth/me');
  return response.data;
};

// Chat
export const chat = async (request: ChatRequest) => {
  const response = await api.post<ChatResponse>('/chat', request);
  return response.data;
};

// Documents
export const getDocuments = async () => {
  const response = await api.get<Document[]>('/documents');
  return response.data;
};

export const getDocument = async (id: string) => {
  const response = await api.get<Document>(`/documents/${id}`);
  return response.data;
};

export const deleteDocument = async (id: string) => {
  const response = await api.delete(`/documents/${id}`);
  return response.data;
};

export class CorpusIngestionStreamError extends Error {
  constructor(message: string, public readonly jobId?: string) {
    super(message);
    this.name = 'CorpusIngestionStreamError';
  }
}

// Ingestion
export const ingestFile = async (
  file: File,
  metadata: CorpusMetadata,
  onEvent: (event: CorpusProgressEvent) => void,
  signal?: AbortSignal,
): Promise<CorpusProgressEvent> => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('title', metadata.title);
  formData.append('classification', metadata.classification);
  formData.append('source_urls', JSON.stringify(metadata.sourceUrls));
  formData.append('retrieved_at', metadata.retrievedAt);
  formData.append('reuse_basis', metadata.reuseBasis);
  formData.append('synthetic', String(metadata.synthetic));
  if (metadata.synthetic) formData.append('synthetic_label', metadata.syntheticLabel);

  const token = localStorage.getItem('token');
  const response = await fetch('/api/ingest', {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    body: formData,
    signal,
  });
  const jobId = response.headers.get('X-Corpus-Job-ID') || undefined;
  if (!response.ok) {
    let detail = `Ingestion request failed (${response.status})`;
    try {
      const body = await response.json() as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch { /* Keep the safe status-only message. */ }
    throw new CorpusIngestionStreamError(detail, jobId);
  }
  if (!response.body) throw new CorpusIngestionStreamError('Streaming is unavailable in this browser', jobId);

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let lastSequence = 0;
  let terminal: CorpusProgressEvent | null = null;
  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value, { stream: !done }).replace(/\r\n/g, '\n');
      let boundary = buffer.indexOf('\n\n');
      while (boundary >= 0) {
        const frame = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const data = decodeSseFrame(frame);
        if (data) {
          const event = JSON.parse(data) as CorpusProgressEvent;
          if (Number.isFinite(event.sequence) && event.sequence > lastSequence) {
            lastSequence = event.sequence;
            onEvent(event);
            if (event.terminal) terminal = event;
          }
        }
        boundary = buffer.indexOf('\n\n');
      }
      if (done) break;
    }
  } catch (error) {
    if (error instanceof CorpusIngestionStreamError) throw error;
    if (error instanceof DOMException && error.name === 'AbortError') throw error;
    throw new CorpusIngestionStreamError('Progress stream interrupted', jobId);
  }
  if (terminal) return terminal;
  throw new CorpusIngestionStreamError('Progress stream ended before ingestion completed', jobId);
};

export const getCorpusJob = async (jobId: string) => {
  const response = await api.get<CorpusJobSnapshot>(`/admin/corpus/jobs/${jobId}`);
  return response.data;
};

// Admin
export const getUsers = async () => {
  const response = await api.get<User[]>('/admin/users');
  return response.data;
};

export const updateUserRole = async (userId: string, role: RoleUpdate) => {
  const response = await api.patch<User>(`/admin/users/${userId}`, role);
  return response.data;
};

export const getAccessRequests = async () => {
  const response = await api.get<User[]>('/admin/access/requests');
  return response.data;
};

export const reviewAccessRequest = async (userId: string, role: RoleUpdate['role']) => {
  const response = await api.patch<User>(`/admin/access/requests/${userId}`, { role });
  return response.data;
};

export default api;
