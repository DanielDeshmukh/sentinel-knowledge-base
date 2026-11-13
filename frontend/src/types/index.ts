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
  stage: CorpusStage;
  status: CorpusStageStatus;
  timing_ms: number | null;
  message: string | null;
  completed?: number;
  total?: number;
  vectors_written?: number;
  chunk_count?: number;
  diagnostics?: CorpusDiagnostic[];
  error_code?: string;
  terminal?: boolean;
  searchable_at?: string;
  document_id?: string;
}

export type CorpusStage =
  | 'upload' | 'parse' | 'regex_validate' | 'normalize' | 'recheck'
  | 'chunk' | 'embed' | 'stage_vectors' | 'promote' | 'searchable' | 'failed';

export type CorpusStageStatus = 'pending' | 'running' | 'completed' | 'failed';

export interface CorpusDiagnostic {
  code: string;
  severity: 'error' | 'warning';
  message: string;
  line: number | null;
}

export interface CorpusProgressEvent extends IngestionStage {
  job_id: string;
  sequence: number;
  status: CorpusStageStatus;
  diagnostics?: CorpusDiagnostic[];
}

export interface CorpusJobSnapshot {
  id: string;
  document_id: string | null;
  filename: string;
  status: 'running' | 'succeeded' | 'failed';
  stage: CorpusStage;
  sequence: number;
  progress: Partial<CorpusProgressEvent>;
  diagnostics: CorpusDiagnostic[];
  error_code: string | null;
  created_at: string;
  started_at: string;
  finished_at: string | null;
  updated_at: string;
}

export interface CorpusMetadata {
  title: string;
  classification: Document['classification'];
  sourceUrls: string[];
  retrievedAt: string;
  reuseBasis: string;
  synthetic: boolean;
  syntheticLabel: string;
}

export interface RoleUpdate {
  role: 'public' | 'internal' | 'restricted' | 'admin';
}
