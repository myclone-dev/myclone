# Delete User By Email - PostgreSQL Procedure

> **Last Updated**: 2026-01-30
>
> This procedure handles complete user deletion including all related data across all tables.

## Tables Covered

### User-Owned Data (Hard Delete)
| Table | Filter Column | Notes |
|-------|--------------|-------|
| `data_llamaindex_embeddings` | `user_id` | OpenAI embeddings |
| `data_llamalite_embeddings` | `user_id` | Voyage AI embeddings |
| `documents` | `user_id` | Uploaded documents |
| `youtube_videos` | `user_id` | YouTube video imports |
| `voice_clones` | `user_id` | Voice clones |
| `voice_processing_jobs` | `user_id` | Voice processing jobs |
| `widget_tokens` | `user_id` | Widget embed tokens |
| `scraping_jobs` | `user_id` | Scraping job history |
| `linkedin_experiences` | `user_id` | LinkedIn work history |
| `linkedin_posts` | `user_id` | LinkedIn posts |
| `linkedin_basic_info` | `user_id` | LinkedIn profiles |
| `twitter_posts` | via `twitter_profile_id` | Twitter tweets |
| `twitter_profiles` | `user_id` | Twitter profiles |
| `website_scrape_content` | via `scrape_id` | Website page content |
| `website_scrape_metadata` | `user_id` | Website scrape metadata |
| `user_sessions` | `user_email` or `persona_id` | User sessions |
| `user_usage_cache` | `user_id` | Usage tracking cache |
| `platform_stripe_subscriptions` | `user_id` | Stripe subscriptions |
| `user_subscriptions` | `user_id` | Subscription records |
| `stripe_customers` | `user_id` | Stripe customer records |
| `auth_details` | `user_id` | Authentication details |
| `custom_domains` | `user_id` | Custom domain configs |
| `visitor_whitelist` | `user_id` | Visitor whitelist entries |
| `text_sessions` | `persona_owner_id` | Text chat sessions |

### Persona-Related Data (Hard Delete)
| Table | Filter Column | Notes |
|-------|--------------|-------|
| `active_rooms` | `persona_id` | LiveKit active rooms |
| `persona_access_otps` | `persona_id` | OTP verification tokens |
| `workflow_sessions` | `persona_id` | Workflow execution sessions |
| `persona_workflows` | `persona_id` | Workflow definitions |
| `persona_pricing` | `persona_id` | Monetization pricing |
| `conversation_attachments` | via `conversation_id` | Chat file attachments |
| `conversations` | `persona_id` | Chat conversations |
| `patterns` | `persona_id` | Conversation patterns |
| `persona_prompts_history` | `persona_id` | Prompt version history |
| `persona_prompts` | `persona_id` | Active prompts |
| `prompt_templates` | `persona_id` | Prompt templates |
| `persona_data_sources` | `persona_id` | Data source mappings |
| `persona_visitors` | `persona_id` or `visitor_id` | Visitor access junction |
| `personas` | `user_id` | Persona records |

### Soft Delete (Preserve for Audit/Compliance)
| Table | Filter Column | Action | Notes |
|-------|--------------|--------|-------|
| `persona_access_purchases` | `persona_id` or `purchasing_user_id` | SET `deleted_at`, `deleted_reason` | Financial records for tax/audit |
| `workflow_templates` | `created_by` | SET `created_by = NULL` | Preserve system templates |

### Tables NOT Deleted (Global/Config)
| Table | Reason |
|-------|--------|
| `waitlist` | Not linked to users |
| `tier_plans` | Configuration table |
| `stripe_webhook_events` | Global audit logs |
| `worker_processes` | Ephemeral runtime table |

## Usage

```sql
-- Execute the function
SELECT * FROM delete_user_by_email('user@example.com');

-- Returns:
-- success: true/false
-- message: Status message
-- user_id: Deleted user's UUID
-- username: Deleted user's username
-- deleted_counts: JSONB with counts per table
```

## Procedure

```sql
DROP FUNCTION IF EXISTS public.delete_user_by_email(text);

CREATE OR REPLACE FUNCTION public.delete_user_by_email(p_email text)
RETURNS TABLE(success boolean, message text, user_id uuid, username text, deleted_counts jsonb)
LANGUAGE plpgsql
AS $function$
DECLARE
    v_user_id UUID;
    v_username TEXT;
    v_persona_ids UUID[];
    v_counts JSONB := '{}';
    v_count INT;
BEGIN
    -- Find user by email
    SELECT id, users.username INTO v_user_id, v_username
    FROM users
    WHERE email = p_email;

    IF v_user_id IS NULL THEN
        RETURN QUERY SELECT
            FALSE,
            'User not found with email: ' || p_email,
            NULL::UUID,
            NULL::TEXT,
            NULL::JSONB;
        RETURN;
    END IF;

    RAISE NOTICE 'Found user: % (ID: %)', v_username, v_user_id;

    -- Get all persona IDs for this user
    SELECT ARRAY_AGG(p.id) INTO v_persona_ids FROM personas p WHERE p.user_id = v_user_id;
    v_counts := jsonb_set(v_counts, '{personas}', to_jsonb(COALESCE(array_length(v_persona_ids, 1), 0)));

    -- ===== DELETE USER-OWNED DATA =====

    -- Embeddings - OpenAI (user-owned)
    DELETE FROM data_llamaindex_embeddings e WHERE e.user_id = v_user_id;
    GET DIAGNOSTICS v_count = ROW_COUNT;
    v_counts := jsonb_set(v_counts, '{embeddings_llamaindex}', to_jsonb(v_count));

    -- Embeddings - Voyage AI (user-owned)
    DELETE FROM data_llamalite_embeddings e WHERE e.user_id = v_user_id;
    GET DIAGNOSTICS v_count = ROW_COUNT;
    v_counts := jsonb_set(v_counts, '{embeddings_llamalite}', to_jsonb(v_count));

    -- Documents
    DELETE FROM documents d WHERE d.user_id = v_user_id;
    GET DIAGNOSTICS v_count = ROW_COUNT;
    v_counts := jsonb_set(v_counts, '{documents}', to_jsonb(v_count));

    -- YouTube videos
    DELETE FROM youtube_videos y WHERE y.user_id = v_user_id;
    GET DIAGNOSTICS v_count = ROW_COUNT;
    v_counts := jsonb_set(v_counts, '{youtube_videos}', to_jsonb(v_count));

    -- Voice clones
    DELETE FROM voice_clones vc WHERE vc.user_id = v_user_id;
    GET DIAGNOSTICS v_count = ROW_COUNT;
    v_counts := jsonb_set(v_counts, '{voice_clones}', to_jsonb(v_count));

    -- Voice processing jobs
    DELETE FROM voice_processing_jobs vpj WHERE vpj.user_id = v_user_id;
    GET DIAGNOSTICS v_count = ROW_COUNT;
    v_counts := jsonb_set(v_counts, '{voice_processing_jobs}', to_jsonb(v_count));

    -- Widget tokens
    DELETE FROM widget_tokens wt WHERE wt.user_id = v_user_id;
    GET DIAGNOSTICS v_count = ROW_COUNT;
    v_counts := jsonb_set(v_counts, '{widget_tokens}', to_jsonb(v_count));

    -- Scraping jobs
    DELETE FROM scraping_jobs sj WHERE sj.user_id = v_user_id;
    GET DIAGNOSTICS v_count = ROW_COUNT;
    v_counts := jsonb_set(v_counts, '{scraping_jobs}', to_jsonb(v_count));

    -- LinkedIn data
    DELETE FROM linkedin_experiences le WHERE le.user_id = v_user_id;
    GET DIAGNOSTICS v_count = ROW_COUNT;
    v_counts := jsonb_set(v_counts, '{linkedin_experiences}', to_jsonb(v_count));

    DELETE FROM linkedin_posts lp WHERE lp.user_id = v_user_id;
    GET DIAGNOSTICS v_count = ROW_COUNT;
    v_counts := jsonb_set(v_counts, '{linkedin_posts}', to_jsonb(v_count));

    DELETE FROM linkedin_basic_info lb WHERE lb.user_id = v_user_id;
    GET DIAGNOSTICS v_count = ROW_COUNT;
    v_counts := jsonb_set(v_counts, '{linkedin_profiles}', to_jsonb(v_count));

    -- Twitter data (posts first, then profiles)
    DELETE FROM twitter_posts tp WHERE tp.twitter_profile_id IN (
        SELECT tpr.id FROM twitter_profiles tpr WHERE tpr.user_id = v_user_id
    );
    GET DIAGNOSTICS v_count = ROW_COUNT;
    v_counts := jsonb_set(v_counts, '{twitter_posts}', to_jsonb(v_count));

    DELETE FROM twitter_profiles tpr WHERE tpr.user_id = v_user_id;
    GET DIAGNOSTICS v_count = ROW_COUNT;
    v_counts := jsonb_set(v_counts, '{twitter_profiles}', to_jsonb(v_count));

    -- Website data (content first, then metadata)
    DELETE FROM website_scrape_content wsc WHERE wsc.scrape_id IN (
        SELECT wsm.id FROM website_scrape_metadata wsm WHERE wsm.user_id = v_user_id
    );
    GET DIAGNOSTICS v_count = ROW_COUNT;
    v_counts := jsonb_set(v_counts, '{website_pages}', to_jsonb(v_count));

    DELETE FROM website_scrape_metadata wsm WHERE wsm.user_id = v_user_id;
    GET DIAGNOSTICS v_count = ROW_COUNT;
    v_counts := jsonb_set(v_counts, '{website_scrapes}', to_jsonb(v_count));

    -- User sessions (delete by email and persona_id)
    DELETE FROM user_sessions us WHERE us.user_email = p_email OR us.persona_id = ANY(v_persona_ids);
    GET DIAGNOSTICS v_count = ROW_COUNT;
    v_counts := jsonb_set(v_counts, '{user_sessions}', to_jsonb(v_count));

    -- Usage cache
    DELETE FROM user_usage_cache uuc WHERE uuc.user_id = v_user_id;
    GET DIAGNOSTICS v_count = ROW_COUNT;
    v_counts := jsonb_set(v_counts, '{usage_cache}', to_jsonb(v_count));

    -- Platform Stripe subscriptions (delete before user_subscriptions due to FK)
    DELETE FROM platform_stripe_subscriptions pss WHERE pss.user_id = v_user_id;
    GET DIAGNOSTICS v_count = ROW_COUNT;
    v_counts := jsonb_set(v_counts, '{platform_stripe_subscriptions}', to_jsonb(v_count));

    -- User subscriptions
    DELETE FROM user_subscriptions usub WHERE usub.user_id = v_user_id;
    GET DIAGNOSTICS v_count = ROW_COUNT;
    v_counts := jsonb_set(v_counts, '{subscriptions}', to_jsonb(v_count));

    -- Stripe customers
    DELETE FROM stripe_customers sc WHERE sc.user_id = v_user_id;
    GET DIAGNOSTICS v_count = ROW_COUNT;
    v_counts := jsonb_set(v_counts, '{stripe_customers}', to_jsonb(v_count));

    -- Auth details
    DELETE FROM auth_details ad WHERE ad.user_id = v_user_id;
    GET DIAGNOSTICS v_count = ROW_COUNT;
    v_counts := jsonb_set(v_counts, '{auth_details}', to_jsonb(v_count));

    -- Custom domains (user-level)
    DELETE FROM custom_domains cd WHERE cd.user_id = v_user_id;
    GET DIAGNOSTICS v_count = ROW_COUNT;
    v_counts := jsonb_set(v_counts, '{custom_domains}', to_jsonb(v_count));

    -- Visitor whitelist (delete junction table entries first)
    DELETE FROM persona_visitors pv WHERE pv.visitor_id IN (
        SELECT vw.id FROM visitor_whitelist vw WHERE vw.user_id = v_user_id
    );
    GET DIAGNOSTICS v_count = ROW_COUNT;
    v_counts := jsonb_set(v_counts, '{persona_visitors_by_whitelist}', to_jsonb(v_count));

    -- Then delete whitelist entries
    DELETE FROM visitor_whitelist vw WHERE vw.user_id = v_user_id;
    GET DIAGNOSTICS v_count = ROW_COUNT;
    v_counts := jsonb_set(v_counts, '{visitor_whitelist}', to_jsonb(v_count));

    -- Text sessions (user as persona owner)
    DELETE FROM text_sessions ts WHERE ts.persona_owner_id = v_user_id;
    GET DIAGNOSTICS v_count = ROW_COUNT;
    v_counts := jsonb_set(v_counts, '{text_sessions}', to_jsonb(v_count));

    -- Workflow templates (soft delete - SET NULL created_by to preserve system templates)
    UPDATE workflow_templates wt
    SET created_by = NULL
    WHERE wt.created_by = v_user_id;
    GET DIAGNOSTICS v_count = ROW_COUNT;
    v_counts := jsonb_set(v_counts, '{workflow_templates_orphaned}', to_jsonb(v_count));

    -- ===== DELETE PERSONA-RELATED DATA (before deleting personas) =====
    IF v_persona_ids IS NOT NULL THEN
        -- Active rooms (linked to personas)
        DELETE FROM active_rooms ar WHERE ar.persona_id = ANY(v_persona_ids);
        GET DIAGNOSTICS v_count = ROW_COUNT;
        v_counts := jsonb_set(v_counts, '{active_rooms}', to_jsonb(v_count));

        -- Persona access OTPs
        DELETE FROM persona_access_otps pao WHERE pao.persona_id = ANY(v_persona_ids);
        GET DIAGNOSTICS v_count = ROW_COUNT;
        v_counts := jsonb_set(v_counts, '{persona_access_otps}', to_jsonb(v_count));

        -- Workflow sessions (delete before persona_workflows due to FK)
        DELETE FROM workflow_sessions ws WHERE ws.persona_id = ANY(v_persona_ids);
        GET DIAGNOSTICS v_count = ROW_COUNT;
        v_counts := jsonb_set(v_counts, '{workflow_sessions}', to_jsonb(v_count));

        -- Persona workflows
        DELETE FROM persona_workflows pw WHERE pw.persona_id = ANY(v_persona_ids);
        GET DIAGNOSTICS v_count = ROW_COUNT;
        v_counts := jsonb_set(v_counts, '{persona_workflows}', to_jsonb(v_count));

        -- Persona access purchases (soft delete - preserve financial records for tax/audit)
        UPDATE persona_access_purchases pap
        SET deleted_at = NOW(),
            deleted_reason = 'user_deletion'
        WHERE pap.persona_id = ANY(v_persona_ids) OR pap.purchasing_user_id = v_user_id;
        GET DIAGNOSTICS v_count = ROW_COUNT;
        v_counts := jsonb_set(v_counts, '{persona_access_purchases_soft_deleted}', to_jsonb(v_count));

        -- Persona pricing
        DELETE FROM persona_pricing pp WHERE pp.persona_id = ANY(v_persona_ids);
        GET DIAGNOSTICS v_count = ROW_COUNT;
        v_counts := jsonb_set(v_counts, '{persona_pricing}', to_jsonb(v_count));

        -- Conversation attachments (delete before conversations due to FK)
        DELETE FROM conversation_attachments ca WHERE ca.conversation_id IN (
            SELECT c.id FROM conversations c WHERE c.persona_id = ANY(v_persona_ids)
        );
        GET DIAGNOSTICS v_count = ROW_COUNT;
        v_counts := jsonb_set(v_counts, '{conversation_attachments}', to_jsonb(v_count));

        -- Delete conversations
        DELETE FROM conversations c WHERE c.persona_id = ANY(v_persona_ids);
        GET DIAGNOSTICS v_count = ROW_COUNT;
        v_counts := jsonb_set(v_counts, '{conversations}', to_jsonb(v_count));

        -- Delete patterns
        DELETE FROM patterns p WHERE p.persona_id = ANY(v_persona_ids);
        GET DIAGNOSTICS v_count = ROW_COUNT;
        v_counts := jsonb_set(v_counts, '{patterns}', to_jsonb(v_count));

        -- Delete persona prompts history
        DELETE FROM persona_prompts_history pph WHERE pph.persona_id = ANY(v_persona_ids);
        GET DIAGNOSTICS v_count = ROW_COUNT;
        v_counts := jsonb_set(v_counts, '{persona_prompts_history}', to_jsonb(v_count));

        -- Delete persona prompts
        DELETE FROM persona_prompts pp WHERE pp.persona_id = ANY(v_persona_ids);
        GET DIAGNOSTICS v_count = ROW_COUNT;
        v_counts := jsonb_set(v_counts, '{persona_prompts}', to_jsonb(v_count));

        -- Delete prompt templates
        DELETE FROM prompt_templates pt WHERE pt.persona_id = ANY(v_persona_ids);
        GET DIAGNOSTICS v_count = ROW_COUNT;
        v_counts := jsonb_set(v_counts, '{prompt_templates}', to_jsonb(v_count));

        -- Delete persona data sources
        DELETE FROM persona_data_sources pds WHERE pds.persona_id = ANY(v_persona_ids);
        GET DIAGNOSTICS v_count = ROW_COUNT;
        v_counts := jsonb_set(v_counts, '{persona_data_sources}', to_jsonb(v_count));

        -- Persona visitors (junction table - delete visitor access to user's personas)
        DELETE FROM persona_visitors pv WHERE pv.persona_id = ANY(v_persona_ids);
        GET DIAGNOSTICS v_count = ROW_COUNT;
        v_counts := jsonb_set(v_counts, '{persona_visitors_by_persona}', to_jsonb(v_count));

        -- Delete personas
        DELETE FROM personas per WHERE per.id = ANY(v_persona_ids);
        GET DIAGNOSTICS v_count = ROW_COUNT;
        v_counts := jsonb_set(v_counts, '{personas_deleted}', to_jsonb(v_count));
    END IF;

    -- ===== DELETE USER =====
    DELETE FROM users u WHERE u.id = v_user_id;
    GET DIAGNOSTICS v_count = ROW_COUNT;
    v_counts := jsonb_set(v_counts, '{user}', to_jsonb(v_count));

    RAISE NOTICE 'User deleted: % (ID: %)', v_username, v_user_id;
    RAISE NOTICE 'Deletion counts: %', v_counts;

    -- Return success
    RETURN QUERY SELECT
        TRUE,
        'User and all related data deleted successfully',
        v_user_id,
        v_username,
        v_counts;

EXCEPTION
    WHEN OTHERS THEN
        RAISE NOTICE 'Error occurred: %', SQLERRM;
        RETURN QUERY SELECT
            FALSE,
            'Error: ' || SQLERRM,
            v_user_id,
            v_username,
            v_counts;
END;
$function$;
```
