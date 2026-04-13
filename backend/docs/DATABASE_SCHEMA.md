# Database Schema Reference

**Database:** expert-clone-v2-test (PostgreSQL 15+ with pgvector)
**Last Updated:** 2025-01-11

---

## Architecture Overview

**Data Ownership Model:**
- **Users** own all data (LinkedIn, Twitter, documents, embeddings)
- **Personas** select which data sources to use via `persona_data_sources` junction table
- **Embeddings** stored in `data_llamaindex_embeddings` (user-owned, shared across personas)
- **Source tables contain raw data only** - no embeddings
- **LlamaIndex** manages vector embeddings with pgvector HNSW indexes

**Total Tables:** 26 (content_chunks removed in favor of user-owned embeddings)

---

## Core Tables

### users
Central user accounts - owns all enriched data

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | NOT NULL | gen_random_uuid() | Primary key |
| email | text | NOT NULL | - | User email (unique) |
| username | text | NOT NULL | - | Username (unique) |
| fullname | text | NOT NULL | - | User's full name |
| avatar | text | NULL | - | Profile picture URL |
| linkedin_id | text | NULL | - | LinkedIn profile ID (unique) |
| linkedin_url | text | NULL | - | LinkedIn profile URL |
| location | text | NULL | - | User location |
| email_confirmed | boolean | NOT NULL | false | Email verification status |
| created_at | timestamptz | NOT NULL | now() | Creation timestamp |
| updated_at | timestamptz | NOT NULL | now() | Last update timestamp |

**Indexes:**
- `users_pkey` PRIMARY KEY (id)
- `uq_users_email` UNIQUE (email)
- `uq_users_username` UNIQUE (username)
- `uq_users_linkedin_id` UNIQUE (linkedin_id)
- `idx_users_email` btree (email)
- `idx_users_username` btree (username)
- `idx_users_linkedin_id` btree (linkedin_id) WHERE linkedin_id IS NOT NULL

**Relationships:**
- → `personas` (1:N, CASCADE)
- → `auth_details` (1:N, CASCADE)
- → `linkedin_basic_info` (1:1, CASCADE)
- → `linkedin_posts` (1:N, CASCADE)
- → `linkedin_experiences` (1:N, CASCADE)
- → `twitter_profiles` (1:N, SET NULL)
- → `documents` (1:N, CASCADE)
- → `website_scrape_metadata` (1:N, CASCADE)
- → `enrichment_audit_log` (1:N, CASCADE)

**Model:** `app/database/models/user.py`

---

### personas
AI persona configurations - multiple per user

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | NOT NULL | - | Primary key |
| user_id | uuid | NULL | - | Owner user (FK to users.id) |
| username | varchar(255) | NOT NULL | - | Unique username for routing |
| name | varchar(255) | NOT NULL | - | Display name |
| role | varchar(255) | NULL | - | Professional role |
| company | varchar(255) | NULL | - | Company affiliation |
| description | text | NULL | - | Persona description |
| voice_id | varchar(255) | NULL | - | ElevenLabs voice ID |
| created_at | timestamptz | NOT NULL | - | Creation timestamp |
| updated_at | timestamptz | NOT NULL | - | Last update timestamp |

**Indexes:**
- `personas_pkey` PRIMARY KEY (id)
- `personas_username_key` UNIQUE (username)
- `idx_personas_user_id` btree (user_id)

**Relationships:**
- → `user` (N:1)
- → `conversations` (1:N)
- → `patterns` (1:N)
- → `persona_data_sources` (1:N, CASCADE)
- → `user_sessions` (1:N, CASCADE)
- → `active_rooms` (1:N)

**Model:** `app/database/models/database.py`

---

### auth_details
OAuth tokens per platform (encrypted at app level)

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | NOT NULL | gen_random_uuid() | Primary key |
| user_id | uuid | NOT NULL | - | FK to users.id |
| platform | text | NOT NULL | - | google, linkedin, github, twitter |
| platform_user_id | text | NOT NULL | - | User ID on platform |
| platform_username | text | NOT NULL | - | Username on platform |
| avatar | text | NOT NULL | - | Profile picture from platform |
| access_token | text | NOT NULL | - | OAuth access token |
| refresh_token | text | NULL | - | OAuth refresh token |
| token_expiry | timestamptz | NOT NULL | - | Token expiration |
| metadata | jsonb | NOT NULL | {} | Additional platform data |
| created_at | timestamptz | NOT NULL | now() | Creation timestamp |
| updated_at | timestamptz | NOT NULL | now() | Last update timestamp |

**Constraints:**
- `uq_auth_details_user_platform` UNIQUE (user_id, platform)
- `ck_auth_details_valid_platform` CHECK (platform IN ('google', 'linkedin', 'github', 'twitter'))

**Indexes:**
- `auth_details_pkey` PRIMARY KEY (id)
- `idx_auth_details_user_id` btree (user_id)

**Relationships:**
- → `user` (N:1)

**Model:** `app/database/models/user.py`

---

## Data Source Tables

### LinkedIn Tables

#### linkedin_basic_info
LinkedIn profile - one per user

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | NOT NULL | gen_random_uuid() | Primary key |
| user_id | uuid | NOT NULL | - | FK to users.id (UNIQUE) |
| headline | text | NULL | - | LinkedIn headline |
| summary | text | NULL | - | About section |
| profile_picture_url | text | NULL | - | Profile picture URL |
| skills | jsonb | NOT NULL | [] | Skills array |
| location | text | NULL | - | Location |
| industry | text | NULL | - | Industry |
| connections_count | integer | NULL | - | Connections count |
| followers_count | integer | NULL | - | Followers count |
| last_synced_at | timestamptz | NULL | - | Last sync timestamp |
| created_at | timestamptz | NOT NULL | now() | Creation timestamp |
| updated_at | timestamptz | NOT NULL | now() | Last update timestamp |

**Indexes:**
- `linkedin_basic_info_pkey` PRIMARY KEY (id)
- `uq_linkedin_basic_info_user_id` UNIQUE (user_id)
- `idx_linkedin_basic_info_user_id` btree (user_id)

**Relationships:**
- → `user` (1:1)

**Model:** `app/database/models/linkedin.py`

---

#### linkedin_posts
LinkedIn posts - raw text only (embeddings in data_llamaindex_embeddings)

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | NOT NULL | gen_random_uuid() | Primary key |
| user_id | uuid | NOT NULL | - | FK to users.id |
| linkedin_post_id | text | NOT NULL | - | LinkedIn post ID (UNIQUE) |
| text | text | NULL | - | Post content |
| post_url | text | NULL | - | Post URL |
| num_likes | integer | NOT NULL | 0 | Likes count |
| num_comments | integer | NOT NULL | 0 | Comments count |
| num_reposts | integer | NOT NULL | 0 | Reposts count |
| posted_at | timestamptz | NULL | - | Post timestamp |
| created_at | timestamptz | NOT NULL | now() | Creation timestamp |
| updated_at | timestamptz | NOT NULL | now() | Last update timestamp |

**Indexes:**
- `linkedin_posts_pkey` PRIMARY KEY (id)
- `uq_linkedin_posts_linkedin_post_id` UNIQUE (linkedin_post_id)
- `idx_linkedin_posts_user_id` btree (user_id)
- `idx_linkedin_posts_posted_at` btree (posted_at DESC)

**Relationships:**
- → `user` (N:1)

**Model:** `app/database/models/linkedin.py`

---

#### linkedin_experiences
Work experience history

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | NOT NULL | gen_random_uuid() | Primary key |
| user_id | uuid | NOT NULL | - | FK to users.id |
| company | text | NOT NULL | - | Company name |
| company_linkedin_url | text | NULL | - | Company LinkedIn URL |
| title | text | NOT NULL | - | Job title |
| location | text | NULL | - | Job location |
| description | text | NULL | - | Role description |
| start_date | date | NULL | - | Start date |
| end_date | date | NULL | - | End date |
| is_current | boolean | NOT NULL | false | Currently employed |
| created_at | timestamptz | NOT NULL | now() | Creation timestamp |
| updated_at | timestamptz | NOT NULL | now() | Last update timestamp |

**Constraints:**
- `uq_linkedin_experiences_user_company_title` UNIQUE (user_id, company, title)

**Indexes:**
- `linkedin_experiences_pkey` PRIMARY KEY (id)
- `idx_linkedin_experiences_user_id` btree (user_id)
- `idx_linkedin_experiences_current` btree (user_id) WHERE is_current = true

**Relationships:**
- → `user` (N:1)

**Model:** `app/database/models/linkedin.py`

---

### Twitter Tables

#### twitter_profiles
Twitter profile - one per user

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | NOT NULL | gen_random_uuid() | Primary key |
| user_id | uuid | NULL | - | FK to users.id |
| twitter_id | text | NOT NULL | - | Twitter user ID (UNIQUE) |
| username | text | NOT NULL | - | Twitter handle (UNIQUE) |
| display_name | text | NULL | - | Display name |
| bio | text | NULL | - | Bio |
| profile_image_url | text | NULL | - | Profile image URL |
| verified | boolean | NOT NULL | false | Verified status |
| followers_count | integer | NOT NULL | 0 | Followers count |
| following_count | integer | NOT NULL | 0 | Following count |
| tweet_count | integer | NOT NULL | 0 | Total tweets |
| location | text | NULL | - | Location |
| website_url | text | NULL | - | Website URL |
| joined_date | date | NULL | - | Account creation date |
| last_scraped_at | timestamptz | NOT NULL | now() | Last scrape timestamp |
| created_at | timestamptz | NOT NULL | now() | Creation timestamp |
| updated_at | timestamptz | NOT NULL | now() | Last update timestamp |

**Indexes:**
- `twitter_profiles_pkey` PRIMARY KEY (id)
- `uq_twitter_profiles_twitter_id` UNIQUE (twitter_id)
- `uq_twitter_profiles_username` UNIQUE (username)
- `idx_twitter_profiles_user_id` btree (user_id)
- `idx_twitter_profiles_twitter_id` btree (twitter_id)

**Relationships:**
- → `user` (N:1)
- → `twitter_posts` (1:N)

**Model:** `app/database/models/twitter.py`

---

#### twitter_posts
Twitter posts - raw text only (embeddings in data_llamaindex_embeddings)

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | NOT NULL | gen_random_uuid() | Primary key |
| twitter_profile_id | uuid | NULL | - | FK to twitter_profiles.id |
| tweet_id | text | NOT NULL | - | Tweet ID (UNIQUE) |
| content | text | NOT NULL | - | Tweet content |
| tweet_url | text | NULL | - | Tweet URL |
| reply_to_tweet_id | text | NULL | - | Reply to tweet ID |
| retweet_of_tweet_id | text | NULL | - | Retweeted tweet ID |
| num_likes | integer | NOT NULL | 0 | Likes count |
| num_retweets | integer | NOT NULL | 0 | Retweets count |
| num_replies | integer | NOT NULL | 0 | Replies count |
| num_views | integer | NOT NULL | 0 | Views count |
| posted_at | timestamptz | NOT NULL | - | Tweet timestamp |
| created_at | timestamptz | NOT NULL | now() | Creation timestamp |

**Indexes:**
- `twitter_posts_pkey` PRIMARY KEY (id)
- `uq_twitter_posts_tweet_id` UNIQUE (tweet_id)
- `idx_twitter_posts_profile_id` btree (twitter_profile_id)
- `idx_twitter_posts_posted_at` btree (posted_at DESC)

**Relationships:**
- → `twitter_profile` (N:1)

**Model:** `app/database/models/twitter.py`

---

### Website Tables

#### website_scrape_metadata
Website scraping job metadata

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | NOT NULL | gen_random_uuid() | Primary key |
| user_id | uuid | NULL | - | FK to users.id |
| website_url | text | NOT NULL | - | Target URL |
| scraper | text | NOT NULL | 'firecrawl' | Scraper used |
| scraping_status | text | NOT NULL | 'completed' | Status |
| max_pages_crawled | integer | NOT NULL | 1 | Max pages to crawl |
| pages_crawled | integer | NOT NULL | 1 | Pages crawled |
| error_message | text | NULL | - | Error message |
| title | text | NULL | - | Website title |
| description | text | NULL | - | Website description |
| language | text | NULL | - | Content language |
| author | text | NULL | - | Author |
| scraped_at | timestamptz | NOT NULL | now() | Scrape timestamp |
| created_at | timestamptz | NOT NULL | now() | Creation timestamp |

**Constraints:**
- `ck_website_scrape_metadata_valid_status` CHECK (scraping_status IN ('pending', 'in_progress', 'completed', 'failed'))

**Indexes:**
- `website_scrape_metadata_pkey` PRIMARY KEY (id)
- `idx_website_scrape_metadata_user_id` btree (user_id)
- `idx_website_scrape_metadata_status` btree (scraping_status)

**Relationships:**
- → `user` (N:1)
- → `website_scrape_content` (1:N)

**Model:** `app/database/models/website.py`

---

#### website_scrape_content
Individual scraped pages - raw content only (embeddings in data_llamaindex_embeddings)

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | NOT NULL | gen_random_uuid() | Primary key |
| scrape_id | uuid | NULL | - | FK to website_scrape_metadata.id |
| page_url | text | NOT NULL | - | Page URL |
| page_title | text | NULL | - | Page title |
| content_markdown | text | NULL | - | Markdown content |
| content_html | text | NULL | - | HTML content |
| content_text | text | NULL | - | Plain text content |
| page_order | integer | NOT NULL | 1 | Page order |
| scraped_at | timestamptz | NOT NULL | now() | Scrape timestamp |
| created_at | timestamptz | NOT NULL | now() | Creation timestamp |

**Indexes:**
- `website_scrape_content_pkey` PRIMARY KEY (id)
- `idx_website_scrape_content_scrape_id` btree (scrape_id)
- `idx_website_scrape_content_page_order` btree (scrape_id, page_order)

**Relationships:**
- → `website_scrape_metadata` (N:1)

**Model:** `app/database/models/website.py`

---

### Document Tables

#### documents
Document storage (PDF, Excel, PowerPoint, etc.) - raw data only (embeddings in data_llamaindex_embeddings)

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | NOT NULL | gen_random_uuid() | Primary key |
| user_id | uuid | NOT NULL | - | FK to users.id |
| document_type | text | NOT NULL | - | pdf, xlsx, pptx, docx, csv, txt, md |
| filename | text | NOT NULL | - | Original filename |
| file_size | integer | NULL | - | File size in bytes |
| content_text | text | NULL | - | Extracted text |
| metadata | jsonb | NOT NULL | {} | Document metadata |
| uploaded_at | timestamptz | NOT NULL | now() | Upload timestamp |
| created_at | timestamptz | NOT NULL | now() | Creation timestamp |
| updated_at | timestamptz | NOT NULL | now() | Last update timestamp |
| page_count | integer | NULL | COMPUTED | PDF pages (computed from metadata) |
| sheet_count | integer | NULL | COMPUTED | Excel sheets (computed from metadata) |
| slide_count | integer | NULL | COMPUTED | PowerPoint slides (computed from metadata) |

**Computed Columns:**
```sql
page_count = CASE WHEN metadata ? 'page_count'
             THEN (metadata->>'page_count')::int
             ELSE NULL END

sheet_count = CASE WHEN metadata ? 'sheet_count'
              THEN (metadata->>'sheet_count')::int
              ELSE NULL END

slide_count = CASE WHEN metadata ? 'slide_count'
              THEN (metadata->>'slide_count')::int
              ELSE NULL END
```

**Constraints:**
- `ck_documents_valid_type` CHECK (document_type IN ('pdf', 'xlsx', 'pptx', 'docx', 'csv', 'txt', 'md'))
- `ck_documents_valid_pdf_metadata` CHECK (document_type != 'pdf' OR (metadata ? 'page_count' AND page_count > 0))
- `ck_documents_valid_excel_metadata` CHECK (document_type != 'xlsx' OR (metadata ? 'sheet_count' AND sheet_count > 0))
- `ck_documents_valid_pptx_metadata` CHECK (document_type != 'pptx' OR (metadata ? 'slide_count' AND slide_count > 0))

**Indexes:**
- `documents_pkey` PRIMARY KEY (id)
- `idx_documents_user_id` btree (user_id)
- `idx_documents_type` btree (document_type)
- `idx_documents_pdf_pages` btree (page_count) WHERE document_type = 'pdf' AND page_count IS NOT NULL
- `idx_documents_excel_sheets` btree (sheet_count) WHERE document_type = 'xlsx' AND sheet_count IS NOT NULL
- `idx_documents_pptx_slides` btree (slide_count) WHERE document_type = 'pptx' AND slide_count IS NOT NULL

**Relationships:**
- → `user` (N:1)

**Model:** `app/database/models/document.py`

---

## Junction & Audit Tables

### persona_data_sources
**Junction table** - Defines which data sources each persona uses (links to specific source records)

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | NOT NULL | gen_random_uuid() | Primary key |
| persona_id | uuid | NOT NULL | - | FK to personas.id |
| source_type | text | NOT NULL | - | Data source type |
| **source_record_id** | **uuid** | **NULL** | **-** | **Generic FK to source record (linkedin_basic_info.id, twitter_profiles.id, etc.)** |
| enabled | boolean | NOT NULL | true | Source active status |
| source_filters | jsonb | NOT NULL | {} | Optional filters |
| created_at | timestamptz | NOT NULL | now() | Creation timestamp |
| updated_at | timestamptz | NOT NULL | now() | Last update timestamp |
| enabled_at | timestamptz | NULL | - | When enabled |
| disabled_at | timestamptz | NULL | - | When disabled |

**Constraints:**
- `uq_persona_data_sources_persona_source` UNIQUE (persona_id, source_type, **source_record_id**) - Allows multiple sources of same type
- `ck_persona_data_sources_valid_source_type` CHECK (source_type IN ('linkedin', 'twitter', 'website', 'pdf', 'github', 'medium', 'youtube', 'document'))

**Indexes:**
- `persona_data_sources_pkey` PRIMARY KEY (id)
- `idx_persona_data_sources_persona` btree (persona_id)
- `idx_persona_data_sources_enabled` btree (persona_id, enabled)
- `idx_persona_data_sources_source` btree (source_type)
- `idx_persona_data_sources_source_record` btree (source_record_id) - **NEW**

**Relationships:**
- → `persona` (N:1, CASCADE)

**Model:** `app/database/models/scraping.py`

**Notes:**
- `source_record_id` points to the root source (profile/account), not individual posts
- Example: source_type='linkedin', source_record_id=linkedin_basic_info.id
- Embeddings are then created for profile + all posts/experiences from that profile

---

### enrichment_audit_log
Audit trail for enrichment operations (per user)

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | NOT NULL | gen_random_uuid() | Primary key |
| user_id | uuid | NOT NULL | - | FK to users.id |
| source_type | text | NOT NULL | - | Source type |
| enrichment_provider | text | NULL | - | Provider (Proxycurl, Apify, etc.) |
| status | text | NOT NULL | 'completed' | Status |
| error_message | text | NULL | - | Error message |
| linkedin_basic_info_id | uuid | NULL | - | FK to linkedin_basic_info.id |
| scrape_metadata_id | uuid | NULL | - | FK to website_scrape_metadata.id |
| twitter_profile_id | uuid | NULL | - | FK to twitter_profiles.id |
| document_id | uuid | NULL | - | FK to documents.id |
| records_imported | integer | NOT NULL | 0 | Total records imported |
| posts_imported | integer | NOT NULL | 0 | Posts imported |
| experiences_imported | integer | NOT NULL | 0 | Experiences imported |
| pages_imported | integer | NOT NULL | 0 | Pages imported |
| started_at | timestamptz | NOT NULL | now() | Start timestamp |
| completed_at | timestamptz | NULL | - | Completion timestamp |

**Constraints:**
- `ck_enrichment_audit_log_valid_source_type` CHECK (source_type IN ('linkedin', 'twitter', 'website', 'pdf', 'document'))
- `ck_enrichment_audit_log_valid_status` CHECK (status IN ('pending', 'processing', 'completed', 'failed'))

**Indexes:**
- `enrichment_audit_log_pkey` PRIMARY KEY (id)
- `idx_enrichment_audit_user_id` btree (user_id)
- `idx_enrichment_audit_status` btree (user_id, status)
- `idx_enrichment_audit_source` btree (user_id, source_type)
- `idx_enrichment_audit_started` btree (started_at DESC)

**Relationships:**
- → `user` (N:1)
- → `linkedin_basic_info` (N:1, optional)
- → `scrape_metadata` (N:1, optional)
- → `twitter_profile` (N:1, optional)
- → `document` (N:1, optional)

**Model:** `app/database/models/enrichment.py`

---

## RAG & AI Tables

### data_llamaindex_embeddings
**User-owned embedding table** - All vector embeddings stored here (managed by LlamaIndex)

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | bigint | NOT NULL | auto-increment | Primary key (LlamaIndex managed) |
| node_id | varchar | NULL | - | LlamaIndex node identifier |
| text | text | NULL | - | Actual chunk content (same as content field) |
| metadata_ | jsonb | NULL | - | LlamaIndex metadata |
| embedding | vector(512) | NULL | - | Voyage AI 3.5 lite embedding vector |
| **user_id** | **uuid** | **NOT NULL** | **-** | **Owner of embeddings (FK to users.id, CASCADE)** |
| **source** | **text** | **NOT NULL** | **-** | **Platform/origin: 'linkedin', 'twitter', 'website', 'document'** |
| **source_type** | **text** | **NOT NULL** | **-** | **Content type: 'profile', 'post', 'tweet', 'page', 'experience', 'pdf'** |
| **source_record_id** | **uuid** | **NOT NULL** | **-** | **Generic FK to specific content (post_id, tweet_id, page_id, etc.)** |
| chunk_index | integer | NULL | - | Chunk order (0, 1, 2...) |
| **posted_at** | **timestamptz** | **NULL** | **-** | **Original post timestamp (for time-based filtering)** |
| **created_at** | **timestamptz** | **NULL** | **now()** | **When embedded** |

**Foreign Keys:**
- `fk_embeddings_user` FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE

**Indexes:**
- `data_llamaindex_embeddings_pkey` PRIMARY KEY (id)
- `data_llamaindex_embeddings_embedding_idx` HNSW (embedding vector_cosine_ops) - **Vector similarity search**
- `idx_embeddings_user_id` btree (user_id)
- `idx_embeddings_source_record` btree (source_record_id)
- `idx_embeddings_source` btree (source)
- `idx_embeddings_user_source` btree (user_id, source)
- `idx_embeddings_posted_at` btree (posted_at DESC)
- `idx_embeddings_source_chunk` UNIQUE btree (source_record_id, chunk_index) - **Prevents duplicate chunks**

**Architecture Notes:**
- **User-owned**: Embeddings belong to users, shared across all user's personas
- **No duplication**: Multiple personas using same LinkedIn profile = 1x embeddings
- **Generic FKs**: source_record_id can point to any content table (linkedin_posts.id, twitter_posts.id, etc.)
- **One source → Many chunks**: A 3000-char post creates 3-4 embedding rows (all with same source_record_id)

**Field Distinction (`source` vs `source_type`):**
- **`source`**: Platform/origin (WHERE data came from) - Values: `linkedin`, `twitter`, `website`, `document`
- **`source_type`**: Content type (WHAT kind of content) - Values: `profile`, `post`, `tweet`, `page`, `experience`, `pdf`
- **Examples**:
  - `source='linkedin'` + `source_type='profile'` → LinkedIn profile information
  - `source='linkedin'` + `source_type='post'` → A LinkedIn post
  - `source='linkedin'` + `source_type='experience'` → Work experience entry
  - `source='twitter'` + `source_type='profile'` → Twitter bio/profile
  - `source='twitter'` + `source_type='tweet'` → An individual tweet
  - `source='website'` + `source_type='page'` → A scraped webpage
  - `source='document'` + `source_type='pdf'` → A PDF document
- **Use cases**:
  - Filter all LinkedIn content: `WHERE source = 'linkedin'`
  - Filter all posts across platforms: `WHERE source_type = 'post'`
  - Filter LinkedIn posts only: `WHERE source = 'linkedin' AND source_type = 'post'`

**Chunking Config:**
- Chunk size: 1000 characters
- Overlap: 200 characters
- Model: text-embedding-3-small (1536 dimensions)

**Vector Search Query:**
```sql
-- Get embeddings for persona (requires resolution through persona_data_sources)
-- Step 1: Get source_record_ids for persona
WITH persona_sources AS (
  SELECT source_record_id FROM persona_data_sources
  WHERE persona_id = $1 AND enabled = true
),
content_ids AS (
  -- Expand to all content from those sources
  SELECT id FROM linkedin_posts WHERE linkedin_basic_info_id IN (SELECT source_record_id FROM persona_sources)
  UNION ALL
  SELECT source_record_id FROM persona_sources -- Include profile itself
)
SELECT text, metadata_, embedding <=> $2 AS distance
FROM data_llamaindex_embeddings
WHERE source_record_id IN (SELECT * FROM content_ids)
ORDER BY distance
LIMIT 10;
```

**Model:** Managed by LlamaIndex (no SQLAlchemy model)

---

### patterns
Extracted communication/thinking patterns

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | NOT NULL | - | Primary key |
| persona_id | uuid | NOT NULL | - | FK to personas.id |
| pattern_type | varchar(50) | NOT NULL | - | style, thinking, response |
| pattern_data | jsonb | NOT NULL | - | Pattern details |
| confidence | real | NULL | - | Confidence score (0-1) |
| created_at | timestamptz | NOT NULL | - | Creation timestamp |

**Indexes:**
- `patterns_pkey` PRIMARY KEY (id)

**Relationships:**
- → `persona` (N:1)

**Model:** `app/database/models/patterns.py`

---

### conversations
Conversation history

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | NOT NULL | - | Primary key |
| persona_id | uuid | NOT NULL | - | FK to personas.id |
| session_id | varchar(255) | NULL | - | Session identifier |
| user_email | varchar(255) | NULL | - | User email |
| messages | jsonb | NOT NULL | - | Array of {role, content, timestamp} |
| conversation_metadata | jsonb | NULL | - | Additional metadata |
| created_at | timestamptz | NOT NULL | - | Creation timestamp |
| updated_at | timestamptz | NOT NULL | - | Last update timestamp |
| conversation_type | varchar(50) | NOT NULL | - | text or voice |

**Constraints:**
- `check_conversation_type` CHECK (conversation_type IN ('text', 'voice'))

**Indexes:**
- `conversations_pkey` PRIMARY KEY (id)

**Relationships:**
- → `persona` (N:1)

**Model:** `app/database/models/database.py`

---

### prompt_templates
Reusable prompt templates

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | integer | NOT NULL | - | Primary key |
| name | varchar(255) | NOT NULL | - | Template name |
| template | text | NOT NULL | - | Prompt template text |
| variables | jsonb | NULL | - | Template variables |
| created_at | timestamptz | NOT NULL | - | Creation timestamp |
| updated_at | timestamptz | NOT NULL | - | Last update timestamp |

**Indexes:**
- `prompt_templates_pkey` PRIMARY KEY (id)

**Model:** `app/database/models/database.py`

---

### persona_prompts
Persona-specific prompt configurations

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | integer | NOT NULL | - | Primary key |
| persona_id | uuid | NOT NULL | - | FK to personas.id |
| default_prompt | text | NOT NULL | - | Default system prompt |
| rag_prompt | text | NULL | - | RAG-specific prompt |
| context_window | integer | NOT NULL | 10 | Context window size |
| created_at | timestamptz | NOT NULL | - | Creation timestamp |
| updated_at | timestamptz | NOT NULL | - | Last update timestamp |

**Indexes:**
- `persona_prompts_pkey` PRIMARY KEY (id)

**Model:** `app/database/models/database.py`

---

## Session & Auth Tables

### user_sessions
Chat session tracking

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | NOT NULL | - | Primary key |
| persona_id | uuid | NOT NULL | - | FK to personas.id |
| session_token | varchar(255) | NOT NULL | - | Unique session token |
| user_email | varchar(255) | NOT NULL | - | User email |
| message_count | integer | NOT NULL | 0 | Messages in session |
| email_prompted | boolean | NOT NULL | false | Email prompt shown |
| email_provided | boolean | NOT NULL | false | Real email provided |
| is_anonymous | boolean | NOT NULL | true | Anonymous session |
| session_metadata | jsonb | NULL | - | Additional metadata |
| created_at | timestamptz | NOT NULL | - | Creation timestamp |
| updated_at | timestamptz | NOT NULL | - | Last update timestamp |
| last_activity_at | timestamptz | NOT NULL | - | Last activity timestamp |

**Relationships:**
- → `persona` (N:1, CASCADE)

**Model:** `app/database/models/user_session.py`

---

### api_keys
API key management

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | NOT NULL | - | Primary key |
| key_hash | varchar(255) | NOT NULL | - | Hashed API key (UNIQUE) |
| key_prefix | varchar(20) | NOT NULL | - | Key prefix |
| name | varchar(255) | NOT NULL | - | Key name/label |
| scope | apikeyscope | NOT NULL | - | Scope enum |
| description | text | NULL | - | Description |
| is_active | boolean | NOT NULL | - | Active status |
| created_at | timestamptz | NOT NULL | - | Creation timestamp |
| expires_at | timestamptz | NULL | - | Expiration timestamp |
| last_used_at | timestamptz | NULL | - | Last usage timestamp |
| created_by | varchar(255) | NULL | - | Creator |

**Indexes:**
- `api_keys_pkey` PRIMARY KEY (id)
- `api_keys_key_hash_key` UNIQUE (key_hash)

**Model:** `app/database/models/api_keys.py`

---

## System Tables

### active_rooms
LiveKit room management for voice sessions

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | NOT NULL | - | Primary key |
| persona_id | uuid | NOT NULL | - | FK to personas.id |
| room_name | varchar(255) | NOT NULL | - | LiveKit room name |
| participant_identity | varchar(255) | NOT NULL | - | Participant identifier |
| status | varchar(50) | NOT NULL | - | Room status |
| created_at | timestamptz | NOT NULL | - | Creation timestamp |
| updated_at | timestamptz | NOT NULL | - | Last update timestamp |

**Relationships:**
- → `persona` (N:1)

**Model:** `app/database/models/livekit.py`

---

### worker_processes
LiveKit worker process tracking

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | NOT NULL | - | Primary key |
| worker_id | varchar(255) | NOT NULL | - | Worker identifier |
| process_id | integer | NOT NULL | - | OS process ID |
| status | varchar(50) | NOT NULL | - | Worker status |
| started_at | timestamptz | NOT NULL | - | Start timestamp |
| last_heartbeat | timestamptz | NOT NULL | - | Last heartbeat |

**Model:** `app/database/models/livekit.py`

---

### waitlist
Email waitlist

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | NOT NULL | - | Primary key |
| email | varchar(255) | NOT NULL | - | Email (UNIQUE) |
| name | varchar(255) | NULL | - | Name |
| company | varchar(255) | NULL | - | Company |
| use_case | text | NULL | - | Use case description |
| created_at | timestamptz | NOT NULL | - | Creation timestamp |

**Model:** `app/database/models/waitlist.py`

---

### external_data_sources
**STATUS:** DEPRECATED - Replaced by normalized tables + enrichment_audit_log

Will be removed after migration complete.

**Model:** `app/database/models/database.py`

---

### LlamaIndex Tables

**Note:** `data_llamaindex_embeddings` is documented above in "RAG & AI Tables" section.
It's the primary embeddings table, managed by LlamaIndex but with custom columns added for our architecture.

---

### alembic_version
Alembic migration version tracking

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| version_num | varchar(32) | NOT NULL | - | Current migration version |

---

## Entity Relationships

```
users (1) ──→ (N) personas
  │                  │
  │                  ├──→ persona_data_sources [junction] ──→ sources
  │                  ├──→ conversations
  │                  ├──→ patterns
  │                  └──→ user_sessions
  │
  ├──→ data_llamaindex_embeddings [HNSW vector embeddings, user-owned]
  ├──→ auth_details (1:N)
  ├──→ linkedin_basic_info (1:1) ──→ linkedin_posts (1:N)
  │                               └──→ linkedin_experiences (1:N)
  ├──→ twitter_profiles (1:N) ──→ twitter_posts (1:N)
  ├──→ documents (1:N)
  ├──→ website_scrape_metadata (1:N) ──→ website_scrape_content (1:N)
  └──→ enrichment_audit_log (1:N)

Data Flow:
1. User scrapes LinkedIn → linkedin_basic_info + posts
2. Ingestion creates embeddings → data_llamaindex_embeddings (user_id, source_record_id)
3. Persona enables source → persona_data_sources (persona_id, source_record_id)
4. Retrieval resolves: persona → sources → content_ids → embeddings
```

---

## Common Query Patterns

### Get persona's active data sources
```sql
SELECT source_type, enabled, enabled_at
FROM persona_data_sources
WHERE persona_id = $1 AND enabled = true;
```

### Get user's LinkedIn posts
```sql
SELECT lp.text, lp.posted_at, lp.num_likes
FROM linkedin_posts lp
JOIN personas p ON p.user_id = lp.user_id
WHERE p.id = $1
ORDER BY lp.posted_at DESC;
```

### Check enrichment status for user
```sql
SELECT source_type, status, posts_imported, started_at, completed_at
FROM enrichment_audit_log
WHERE user_id = $1
ORDER BY started_at DESC;
```

### Vector search for persona (new architecture)
```sql
-- Step 1: Get enabled sources for persona
WITH persona_sources AS (
  SELECT source_type, source_record_id
  FROM persona_data_sources
  WHERE persona_id = $1 AND enabled = true
),
-- Step 2: Expand to all content IDs from those sources
linkedin_content AS (
  SELECT ps.source_record_id AS id FROM persona_sources ps WHERE ps.source_type = 'linkedin'
  UNION ALL
  SELECT lp.id FROM linkedin_posts lp
  JOIN persona_sources ps ON lp.linkedin_basic_info_id = ps.source_record_id
  WHERE ps.source_type = 'linkedin'
)
-- Step 3: Query embeddings
SELECT e.text, e.metadata_, e.embedding <=> $2 AS distance
FROM data_llamaindex_embeddings e
WHERE e.source_record_id IN (SELECT id FROM linkedin_content)
ORDER BY distance
LIMIT 10;
```

### Count embeddings per source for user
```sql
SELECT source, COUNT(*) as chunks, COUNT(DISTINCT source_record_id) as documents
FROM data_llamaindex_embeddings
WHERE user_id = $1
GROUP BY source;
```

### Delete all embeddings from specific LinkedIn post
```sql
DELETE FROM data_llamaindex_embeddings
WHERE source_record_id = $1;  -- Deletes all chunks from that post
```

---

## References

- **Model Files:** `app/database/models/`
- **Migrations:** `alembic/versions/`
- **Migration Plan:** `docs/DATABASE_MIGRATION_PLAN.md`
- **Architecture:** `docs/architecture/ARCHITECTURE.md`
