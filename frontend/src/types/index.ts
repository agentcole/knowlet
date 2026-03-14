export type TenantRole = "owner" | "admin" | "member" | "viewer";

export interface User {
  id: string;
  email: string;
  full_name: string;
  default_language: string;
  is_active: boolean;
}

export interface Membership {
  tenant_id: string;
  tenant_name: string;
  tenant_slug: string;
  role: TenantRole;
}

export interface TenantMember {
  user_id: string;
  email: string;
  full_name: string;
  role: TenantRole;
}

export interface Tenant {
  id: string;
  name: string;
  slug: string;
  settings: Record<string, unknown> | null;
}

export interface Document {
  id: string;
  filename: string;
  file_type: string;
  status: "uploaded" | "processing" | "processed" | "failed";
  metadata: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export type WikiPlacementAction = "create_new" | "append" | "replace";

export interface WikiPlacement {
  category_name: string;
  page_title: string;
  action: WikiPlacementAction;
  reasoning?: string | null;
  confidence?: number | null;
}

export interface DocumentWikiWorkflow {
  state: string;
  language: string | null;
  suggestion: WikiPlacement | null;
  placement: WikiPlacement | null;
  approved_by: string | null;
  approved_at: string | null;
  published_page_ids: string[] | null;
  revision_note: string | null;
  error: string | null;
}

export interface DocumentChunk {
  id: string;
  chunk_index: number;
  content: string;
  token_count: number;
  metadata: Record<string, unknown> | null;
}

export interface WikiCategory {
  id: string;
  name: string;
  slug: string;
  parent_id: string | null;
  sort_order: number;
  children: WikiCategory[];
  pages: WikiPage[];
}

export interface WikiPage {
  id: string;
  title: string;
  slug: string;
  category_id: string | null;
  sort_order: number;
  markdown_content: string;
  version: number;
  source_documents: string[] | null;
  source_meetings: string[] | null;
}

export interface WikiPageRevision {
  id: string;
  page_id: string;
  version: number;
  title: string;
  markdown_content: string;
  change_note: string | null;
  created_by: string | null;
  created_at: string;
}

export interface WikiTree {
  categories: WikiCategory[];
  uncategorized_pages: WikiPage[];
}

export interface Meeting {
  id: string;
  title: string;
  duration_seconds: number | null;
  status: string;
  meeting_date: string | null;
  participants: string[] | null;
  created_at: string;
}

export interface TranscriptSegment {
  speaker: string;
  start: number;
  end: number;
  text: string;
}

export interface Transcript {
  meeting_id: string;
  full_text: string;
  segments: TranscriptSegment[] | null;
  summary: string | null;
  action_items: Array<{ assignee: string; task: string; deadline?: string }> | null;
}

export interface ChatSession {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources: Array<{
    source_type?: "wiki_page" | "document_chunk" | "document";
    wiki_page_id?: string;
    document_id?: string;
    chunk_id?: string;
    score: number;
    title: string;
    snippet: string;
  }> | null;
  created_at: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export type SearchSourceType = "wiki_page" | "document" | "document_chunk" | "meeting";

export interface SearchResult {
  source_type: SearchSourceType;
  source_id: string;
  title: string;
  snippet: string;
  score: number;
}

export interface SearchResponse {
  results: SearchResult[];
}
