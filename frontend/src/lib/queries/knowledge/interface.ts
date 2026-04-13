/**
 * Knowledge management type definitions
 */

// Data Source Types
export type DataSourceType =
  | "linkedin"
  | "twitter"
  | "website"
  | "pdf"
  | "audio"
  | "video"
  | "youtube";

export type SourceType =
  | "linkedin"
  | "twitter"
  | "website"
  | "document"
  | "youtube";

export type ScrapingStatus =
  | "queued"
  | "pending"
  | "processing"
  | "completed"
  | "failed";

export interface DataSource {
  id: string;
  source_type: DataSourceType;
  source_record_id: string;
  enabled: boolean;
  created_at: string;
  enabled_at: string | null;
  disabled_at: string | null;
}

export interface DataSourcesResponse {
  persona_id: string;
  data_sources: DataSource[];
}

// Knowledge Library Types (New Backend API)
export interface KnowledgeSourceBase {
  id: string;
  type: SourceType;
  display_name: string;
  embeddings_count: number;
  created_at: string;
  updated_at: string;
  used_by_personas_count: number;
}

export interface LinkedInKnowledgeSource extends KnowledgeSourceBase {
  type: "linkedin";
  headline?: string;
  summary?: string;
  location?: string;
  posts_count: number;
  experiences_count: number;
  skills_count: number;
  latest_experience_title?: string;
  last_synced_at?: string;
}

export interface TwitterKnowledgeSource extends KnowledgeSourceBase {
  type: "twitter";
  username: string;
  display_name_twitter?: string;
  bio?: string;
  verified: boolean;
  tweets_count: number;
  followers_count: number;
  following_count: number;
  last_scraped_at?: string;
}

export interface WebsiteKnowledgeSource extends KnowledgeSourceBase {
  type: "website";
  website_url: string;
  title?: string;
  description?: string;
  scraper: string;
  pages_crawled: number;
  max_pages_crawled: number;
  scraping_status: "pending" | "in_progress" | "completed" | "failed";
  scraped_at: string;
}

export interface DocumentKnowledgeSource extends KnowledgeSourceBase {
  type: "document";
  filename: string;
  document_type: "pdf" | "xlsx" | "pptx" | "docx" | "csv" | "txt" | "md";
  file_size?: number;
  page_count?: number;
  sheet_count?: number;
  slide_count?: number;
  uploaded_at: string;
}

export interface YouTubeKnowledgeSource extends KnowledgeSourceBase {
  type: "youtube";
  video_id: string;
  title: string;
  description?: string;
  channel_name?: string;
  duration_seconds?: number;
  has_transcript: boolean;
  published_at?: string;
}

export type KnowledgeSource =
  | LinkedInKnowledgeSource
  | TwitterKnowledgeSource
  | WebsiteKnowledgeSource
  | DocumentKnowledgeSource
  | YouTubeKnowledgeSource;

export interface KnowledgeLibraryResponse {
  linkedin: LinkedInKnowledgeSource[];
  twitter: TwitterKnowledgeSource[];
  websites: WebsiteKnowledgeSource[];
  documents: DocumentKnowledgeSource[];
  youtube: YouTubeKnowledgeSource[];
  total_sources: number;
  total_embeddings: number;
}

export interface KnowledgeSourceDetailResponse {
  source_type: string;
  source_id: string;
  used_by_personas: Array<{
    id: string;
    persona_name: string;
    name: string;
    enabled: boolean;
    attached_at: string;
  }>;
  personas_count: number;
}

export interface DeleteKnowledgeSourceResponse {
  success: boolean;
  source_type: SourceType;
  source_record_id: string;
  embeddings_deleted: number;
  personas_affected: number;
  message: string;
}

// Scraping Job Types
export interface ScrapingJob {
  job_id: string;
  user_id: string;
  source_type: DataSourceType;
  status: ScrapingStatus;
  provider: string | null;
  error_message: string | null;
  records_imported: number;
  posts_imported: number;
  experiences_imported: number;
  pages_imported: number;
  started_at: string;
  completed_at: string | null;
  linkedin_profile_id: string | null;
  twitter_profile_id: string | null;
  website_metadata_id: string | null;
  document_id: string | null;
  youtube_video_id: string | null;
  source_name: string | null;
  file_type: string | null;
}

export interface ScrapingJobsResponse {
  user_id: string;
  total_jobs: number;
  active_jobs: number;
  completed_jobs: number;
  failed_jobs: number;
  jobs: ScrapingJob[];
}

// Expert Status Types
export interface EnrichmentStatus {
  linkedin_completed: boolean;
  website_completed: boolean;
  twitter_completed: boolean;
  pdf_completed: boolean;
}

export interface ExpertStatusResponse {
  username: string;
  persona_id: string;
  enrichment_status: EnrichmentStatus;
  chat_enabled: boolean;
  total_chunks_processed: number;
  last_updated: string;
}

// Upload Request Types
export interface AutoOnboardRequest {
  username: string;
  fullname: string;
  email?: string;
  linkedin_url?: string;
  twitter_username?: string;
  website_url?: string;
  website_max_pages?: number;
}

export interface LinkedInUploadRequest {
  user_id: string;
  linkedin_url: string;
}

export interface TwitterUploadRequest {
  user_id: string;
  twitter_username: string;
}

export interface WebsiteUploadRequest {
  user_id: string;
  website_url: string;
  max_pages?: number;
}

export interface YouTubeUploadRequest {
  youtube_url: string;
  user_id: string;
  persona_id?: string;
}

// Upload Response Types
export interface UploadResponse {
  success: boolean;
  message: string;
  job_id?: string;
  jobs_queued?: Record<string, string>;
  total_jobs?: number;
}

// Document Upload Response (for /api/v1/documents/add endpoint)
export interface DocumentUploadResponse {
  success: boolean;
  message: string;
  document_id?: string;
  job_id?: string;
  supports_enrichment?: boolean;
}

// Document Upload Request
export interface DocumentUploadRequest {
  userId: string;
  file: File;
  personaName?: string;
  force?: boolean;
}

// Batch Document Upload Types
export type BatchFileStatus =
  | "pending"
  | "uploading"
  | "success"
  | "error"
  | "duplicate";

export interface BatchFileItem {
  id: string;
  file: File;
  status: BatchFileStatus;
  progress: number;
  errorMessage?: string;
  documentId?: string;
}

export interface BatchUploadRequest {
  userId: string;
  files: File[];
  personaName?: string;
  force?: boolean;
}

export interface BatchUploadResult {
  totalFiles: number;
  successCount: number;
  errorCount: number;
  duplicateCount: number;
  results: Array<{
    fileName: string;
    status: BatchFileStatus;
    documentId?: string;
    errorMessage?: string;
  }>;
}

// Raw Text Upload Types (for pasting text directly)
export interface RawTextUploadRequest {
  title: string;
  content: string;
  userId: string;
  personaName?: string;
  force?: boolean;
}
