export interface SnapshotItem {
  snapshot_id: string;
  root: string;
  indexed_at: string;
}

export interface IndexResponse {
  snapshot_id: string;
  status: string;
  files: number;
  functions: number;
  calls: number;
  endpoints: number;
}

export interface InvestigateRequest {
  snapshot_id: string;
  question: string;
  target?: string | null;
  provider?: 'none' | 'test' | 'openai' | 'gemini' | 'ollama';
  share_source?: boolean;
  graph?: string | null;
}

export interface AgentThoughtPayload {
  step: string;
  detail: string;
  target?: string | null;
  provider?: string;
  arguments?: Record<string, unknown>;
}

export interface ToolCallPayload {
  tool: string;
  [key: string]: unknown;
}

export interface GraphEvidencePayload {
  paths?: Array<string[] | { functions?: string[]; function_ids?: string[]; evidence_ids?: string[] }>;
  potentially_affected_endpoints?: Array<string | { id?: string; method?: string; path?: string; handler_id?: string; handler_symbol?: string }>;
  [key: string]: unknown;
}

export interface AnalysisGapsPayload {
  unresolved_calls?: Array<Record<string, unknown>>;
  [key: string]: unknown;
}

export interface ImpactReport {
  snapshot_id: string;
  target?: string;
  target_id?: string;
  question: string;
  summary?: string;
  graph_evidence: GraphEvidencePayload;
  analysis_gaps: AnalysisGapsPayload;
  affected_endpoints?: string[];
  recommendations?: string[];
  [key: string]: unknown;
}

export interface EvidenceItem {
  edge_id: string;
  caller_function: string;
  callee_function: string;
  file_path: string;
  line_number: number;
  hash: string;
  source_lines?: string[];
}
