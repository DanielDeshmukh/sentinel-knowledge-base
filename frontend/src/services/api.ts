import axios from 'axios';
import type {
  User,
  TokenResponse,
  Document,
  ChatRequest,
  ChatResponse,
  IngestionResponse,
  RoleUpdate,
} from '../types';

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
export const register = async (displayName: string, email: string, password: string) => {
  const response = await api.post<TokenResponse>('/auth/register', {
    display_name: displayName,
    email,
    password,
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

// Ingestion
export const ingestFile = async (file: File, title: string, classification: string) => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('title', title);
  formData.append('classification', classification);

  const response = await api.post<IngestionResponse>('/ingest', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
};

// Admin
export const getUsers = async () => {
  const response = await api.get<User[]>('/admin/users');
  return response.data;
};

export const updateUserRole = async (userId: string, role: RoleUpdate) => {
  const response = await api.put<User>(`/admin/users/${userId}/role`, role);
  return response.data;
};

export default api;
