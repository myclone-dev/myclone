/**
 * Document management type definitions
 */

export interface Document {
  id: string;
  filename: string;
  document_type: string;
  file_size: number | null;
  uploaded_at: string;
  metadata: Record<string, unknown>;
}

export interface DocumentListResponse {
  documents: Document[];
  total_count: number;
}
