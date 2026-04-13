"""add_stripe_integration_tables

Revision ID: 13b9596d4900
Revises: 7e32f8becad3
Create Date: 2025-12-01 06:20:55.645325

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '13b9596d4900'
down_revision: Union[str, Sequence[str], None] = '7e32f8becad3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Add Stripe integration tables."""

    # ============================================================================
    # STEP 1: Modify Existing Tables
    # ============================================================================

    # Add account_type column to users table (using VARCHAR with CHECK constraint)
    op.execute(sa.text("""
        ALTER TABLE users
        ADD COLUMN account_type VARCHAR(20) NOT NULL DEFAULT 'creator'
        CHECK (account_type IN ('creator', 'visitor'))
    """))

    # Add comment
    op.execute(sa.text("""
        COMMENT ON COLUMN users.account_type IS
        'Account type: creator (creates personas) or visitor (purchases access)'
    """))

    # ============================================================================
    # STEP 3: Create stripe_customers Table (Shared Infrastructure)
    # ============================================================================

    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS stripe_customers (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
            stripe_customer_id VARCHAR(255) NOT NULL UNIQUE,
            stripe_email VARCHAR(255),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """))

    # Create indexes
    op.create_index('idx_stripe_customers_user', 'stripe_customers', ['user_id'])
    op.create_index('idx_stripe_customers_stripe_id', 'stripe_customers', ['stripe_customer_id'])

    # ============================================================================
    # STEP 4: Create platform_stripe_subscriptions Table (Feature 1)
    # ============================================================================

    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS platform_stripe_subscriptions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            user_subscription_id UUID NOT NULL REFERENCES user_subscriptions(id) ON DELETE CASCADE,

            -- Stripe identifiers
            stripe_customer_id VARCHAR(255) NOT NULL,
            stripe_subscription_id VARCHAR(255) NOT NULL UNIQUE,
            stripe_price_id VARCHAR(255) NOT NULL,
            stripe_product_id VARCHAR(255),

            -- Subscription status
            stripe_status VARCHAR(50) NOT NULL,

            -- Billing period
            current_period_start TIMESTAMPTZ NOT NULL,
            current_period_end TIMESTAMPTZ NOT NULL,

            -- Cancellation tracking
            cancel_at_period_end BOOLEAN NOT NULL DEFAULT FALSE,
            cancel_at TIMESTAMPTZ,
            canceled_at TIMESTAMPTZ,
            ended_at TIMESTAMPTZ,

            -- Trial period
            trial_start TIMESTAMPTZ,
            trial_end TIMESTAMPTZ,

            -- Payment details
            latest_invoice_id VARCHAR(255),
            default_payment_method_id VARCHAR(255),

            -- Additional data from Stripe
            stripe_metadata JSONB NOT NULL DEFAULT '{}',

            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """))

    # Create indexes
    op.create_index('idx_platform_stripe_subs_user', 'platform_stripe_subscriptions', ['user_id'])
    op.create_index('idx_platform_stripe_subs_user_subscription', 'platform_stripe_subscriptions', ['user_subscription_id'])
    op.create_index('idx_platform_stripe_subs_stripe_id', 'platform_stripe_subscriptions', ['stripe_subscription_id'])
    op.create_index('idx_platform_stripe_subs_status', 'platform_stripe_subscriptions', ['stripe_status'])

    # Create unique partial index for active subscriptions
    op.execute(sa.text("""
        CREATE UNIQUE INDEX idx_platform_stripe_subs_user_active
        ON platform_stripe_subscriptions(user_id)
        WHERE stripe_status IN ('trialing', 'active')
    """))

    # ============================================================================
    # STEP 4: Create persona_pricing Table (Feature 2)
    # ============================================================================

    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS persona_pricing (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            persona_id UUID NOT NULL UNIQUE REFERENCES personas(id) ON DELETE CASCADE,

            -- Monetization settings
            pricing_model VARCHAR(50) NOT NULL DEFAULT 'free'
                CHECK (pricing_model IN ('free', 'one_time_lifetime', 'one_time_duration', 'subscription_monthly', 'subscription_yearly')),
            is_monetization_enabled BOOLEAN NOT NULL DEFAULT FALSE,

            -- Currency (Phase 1: USD only)
            currency VARCHAR(3) NOT NULL DEFAULT 'usd',

            -- One-time payment settings
            one_time_price_cents INTEGER,
            access_duration_days INTEGER,

            -- Subscription settings
            monthly_price_cents INTEGER,
            yearly_price_cents INTEGER,

            -- Free trial settings (for future implementation)
            trial_enabled BOOLEAN NOT NULL DEFAULT FALSE,
            trial_duration_days INTEGER,
            trial_price_cents INTEGER NOT NULL DEFAULT 0,

            -- Stripe product/price IDs (created programmatically)
            stripe_product_id VARCHAR(255),
            stripe_price_id_one_time VARCHAR(255),
            stripe_price_id_monthly VARCHAR(255),
            stripe_price_id_yearly VARCHAR(255),

            -- Future: Stripe Connect for creator payouts
            stripe_account_id VARCHAR(255),
            platform_fee_percentage NUMERIC(5, 2) DEFAULT 0.00,

            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

            -- Validation constraints
            CONSTRAINT ck_persona_pricing_valid_model CHECK (
                CASE pricing_model
                    WHEN 'free' THEN TRUE
                    WHEN 'one_time_lifetime' THEN one_time_price_cents > 0 AND access_duration_days IS NULL
                    WHEN 'one_time_duration' THEN one_time_price_cents > 0 AND access_duration_days > 0
                    WHEN 'subscription_monthly' THEN monthly_price_cents > 0
                    WHEN 'subscription_yearly' THEN yearly_price_cents > 0
                    ELSE FALSE
                END
            ),
            CONSTRAINT ck_persona_pricing_platform_fee CHECK (
                platform_fee_percentage >= 0 AND platform_fee_percentage <= 100
            ),
            CONSTRAINT ck_persona_pricing_currency_phase1 CHECK (
                currency = 'usd'
            ),
            CONSTRAINT ck_persona_pricing_trial CHECK (
                (trial_enabled = FALSE) OR (trial_enabled = TRUE AND trial_duration_days > 0)
            )
        )
    """))

    # Create indexes
    op.create_index('idx_persona_pricing_persona', 'persona_pricing', ['persona_id'])
    op.create_index('idx_persona_pricing_model', 'persona_pricing', ['pricing_model'])

    # Create partial index for enabled monetization
    op.execute(sa.text("""
        CREATE INDEX idx_persona_pricing_enabled
        ON persona_pricing(is_monetization_enabled)
        WHERE is_monetization_enabled = TRUE
    """))

    # ============================================================================
    # STEP 5: Create persona_access_purchases Table (Feature 2)
    # ============================================================================

    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS persona_access_purchases (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            persona_id UUID REFERENCES personas(id) ON DELETE SET NULL,
            purchasing_user_id UUID REFERENCES users(id) ON DELETE SET NULL,

            -- Purchase details
            pricing_model VARCHAR(50) NOT NULL
                CHECK (pricing_model IN ('free', 'one_time_lifetime', 'one_time_duration', 'subscription_monthly', 'subscription_yearly')),
            currency VARCHAR(3) NOT NULL DEFAULT 'usd',
            amount_cents INTEGER NOT NULL,
            status VARCHAR(50) NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'completed', 'failed', 'expired', 'refunded', 'cancelled')),

            -- Access period
            access_granted_at TIMESTAMPTZ,
            access_expires_at TIMESTAMPTZ,

            -- Stripe payment references
            stripe_customer_id VARCHAR(255),
            stripe_payment_intent_id VARCHAR(255),
            stripe_subscription_id VARCHAR(255),
            stripe_invoice_id VARCHAR(255),
            stripe_charge_id VARCHAR(255),
            stripe_checkout_session_id VARCHAR(255),

            -- Future: Stripe Connect payout tracking
            stripe_transfer_id VARCHAR(255),
            platform_fee_cents INTEGER,
            creator_payout_cents INTEGER,
            payout_status VARCHAR(50),
            payout_completed_at TIMESTAMPTZ,

            -- Refund tracking
            refund_reason TEXT,
            refunded_at TIMESTAMPTZ,
            refund_amount_cents INTEGER,

            -- Soft delete (for GDPR compliance, tax audits, dispute resolution)
            deleted_at TIMESTAMPTZ,
            deleted_reason TEXT,

            -- Metadata
            payment_metadata JSONB NOT NULL DEFAULT '{}',

            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

            -- Phase 1: USD only
            CONSTRAINT ck_persona_purchases_currency_phase1 CHECK (currency = 'usd')
        )
    """))

    # Create indexes (exclude soft-deleted records from performance-critical queries)
    op.execute(sa.text("""
        CREATE INDEX idx_persona_purchases_persona
        ON persona_access_purchases(persona_id)
        WHERE deleted_at IS NULL
    """))

    op.execute(sa.text("""
        CREATE INDEX idx_persona_purchases_user
        ON persona_access_purchases(purchasing_user_id)
        WHERE deleted_at IS NULL
    """))

    op.execute(sa.text("""
        CREATE INDEX idx_persona_purchases_status
        ON persona_access_purchases(status)
        WHERE deleted_at IS NULL
    """))

    op.execute(sa.text("""
        CREATE INDEX idx_persona_purchases_expires
        ON persona_access_purchases(access_expires_at)
        WHERE access_expires_at IS NOT NULL AND deleted_at IS NULL
    """))

    # Regular indexes for Stripe references
    op.create_index('idx_persona_purchases_stripe_payment', 'persona_access_purchases', ['stripe_payment_intent_id'])
    op.create_index('idx_persona_purchases_stripe_sub', 'persona_access_purchases', ['stripe_subscription_id'])
    op.create_index('idx_persona_purchases_stripe_checkout', 'persona_access_purchases', ['stripe_checkout_session_id'])

    # Index for soft-deleted records
    op.execute(sa.text("""
        CREATE INDEX idx_persona_purchases_deleted
        ON persona_access_purchases(deleted_at)
        WHERE deleted_at IS NOT NULL
    """))

    # Unique constraint: one active purchase per user per persona (ignoring soft-deleted)
    # Note: Expiration check happens at query time, not in index predicate (NOW() is non-immutable)
    op.execute(sa.text("""
        CREATE UNIQUE INDEX idx_persona_purchases_active_unique
        ON persona_access_purchases(persona_id, purchasing_user_id)
        WHERE status = 'completed'
        AND deleted_at IS NULL
    """))

    # Add important comments (financial/legal requirements)
    op.execute(sa.text("""
        COMMENT ON COLUMN persona_access_purchases.persona_id IS
        'SET NULL on delete to preserve financial record for tax/audit compliance';

        COMMENT ON COLUMN persona_access_purchases.purchasing_user_id IS
        'SET NULL on delete to preserve financial record (GDPR allows this for legal obligations)';

        COMMENT ON COLUMN persona_access_purchases.deleted_at IS
        'Soft delete timestamp (GDPR, user deletion, fraud) - NEVER hard delete financial records';

        COMMENT ON COLUMN persona_access_purchases.deleted_reason IS
        'Why record was soft-deleted (gdpr_request, user_deletion, fraud, chargeback, etc.)';
    """))

    # ============================================================================
    # STEP 6: Create stripe_webhook_events Table (Shared Infrastructure)
    # ============================================================================

    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS stripe_webhook_events (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            stripe_event_id VARCHAR(255) NOT NULL UNIQUE,
            event_type VARCHAR(100) NOT NULL,
            event_data JSONB NOT NULL,
            processed BOOLEAN NOT NULL DEFAULT FALSE,
            processed_at TIMESTAMPTZ,
            processing_error TEXT,
            retry_count INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """))

    # Create indexes
    op.create_index('idx_stripe_webhook_events_stripe_id', 'stripe_webhook_events', ['stripe_event_id'])
    op.create_index('idx_stripe_webhook_events_type', 'stripe_webhook_events', ['event_type'])
    op.create_index('idx_stripe_webhook_events_processed', 'stripe_webhook_events', ['processed'])
    op.create_index('idx_stripe_webhook_events_created', 'stripe_webhook_events', ['created_at'])


def downgrade() -> None:
    """Downgrade schema - Remove Stripe integration tables."""

    # Drop tables in reverse order
    op.drop_table('stripe_webhook_events')
    op.drop_table('persona_access_purchases')
    op.drop_table('persona_pricing')
    op.drop_table('platform_stripe_subscriptions')
    op.drop_table('stripe_customers')

    # Remove account_type column from users table
    op.execute(sa.text("ALTER TABLE users DROP COLUMN account_type"))
