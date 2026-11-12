export interface User {
  id: string;
  display_name: string;
  email: string;
  role: 'public' | 'internal' | 'restricted' | 'admin';
  approved: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface Document {
  id: string;
  title: string;
  classification: 'public' | 'internal' | 'restricted';
  source: string | null;
  uploaded_by: string | null;
  created_at: string;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface ChatRequest {
  question: string;
  conversation_history: ChatMessage[];
}

export interface Citation {
  chunk_id: string;
  document_id: string;
  document_title: string;
  text: string;
  heading_path: string | null;
}

export interface ChatResponse {
  answer: string;
  citations: Citation[];
  retrieval_time_ms: number;
  response_time_ms: number;
}

export interface IngestionStage {
  stage: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  timing_ms: number | null;
  message: string | null;
}

export interface IngestionResponse {
  document_id: string | null;
  stages: IngestionStage[];
  total_time_ms: number;
  status: 'completed' | 'failed';
}

export interface RoleUpdate {
  role: 'public' | 'internal' | 'restricted' | 'admin';
}
