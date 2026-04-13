"""remove_free_pricing_model

Removes PricingModel.FREE enum value and updates database constraint.
Now monetization is controlled solely by is_monetization_enabled flag.

Revision ID: 46218035de30
Revises: d3e148d9e454
Create Date: 2025-12-27 18:25:54.922948

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '46218035de30'
down_revision: Union[str, Sequence[str], None] = 'd3e148d9e454'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # Step 1: Convert any existing 'free' pricing_model records to 'one_time_lifetime' with disabled flag
    # This preserves records but makes them inactive
    # Set default price to $9.99 (999 cents) to satisfy CHECK constraint
    op.execute("""
        UPDATE persona_pricing
        SET
            pricing_model = 'one_time_lifetime',
            is_monetization_enabled = false,
            one_time_price_cents = COALESCE(one_time_price_cents, 999)
        WHERE pricing_model = 'free'
    """)

    # Step 2: Update the default value for pricing_model from 'free' to 'one_time_lifetime'
    op.alter_column(
        'persona_pricing',
        'pricing_model',
        server_default='one_time_lifetime'
    )

    # Step 3: Drop the old CheckConstraint
    op.drop_constraint('ck_persona_pricing_valid_model', 'persona_pricing', type_='check')

    # Step 4: Create new CheckConstraint without 'free' case
    op.create_check_constraint(
        'ck_persona_pricing_valid_model',
        'persona_pricing',
        """
        CASE pricing_model
            WHEN 'one_time_lifetime' THEN one_time_price_cents > 0 AND access_duration_days IS NULL
            WHEN 'one_time_duration' THEN one_time_price_cents > 0 AND access_duration_days > 0
            WHEN 'subscription_monthly' THEN monthly_price_cents > 0
            WHEN 'subscription_yearly' THEN yearly_price_cents > 0
            ELSE FALSE
        END
        """
    )


def downgrade() -> None:
    """Downgrade schema."""

    # Step 1: Drop the new constraint
    op.drop_constraint('ck_persona_pricing_valid_model', 'persona_pricing', type_='check')

    # Step 2: Recreate old constraint with 'free' case
    op.create_check_constraint(
        'ck_persona_pricing_valid_model',
        'persona_pricing',
        """
        CASE pricing_model
            WHEN 'free' THEN TRUE
            WHEN 'one_time_lifetime' THEN one_time_price_cents > 0 AND access_duration_days IS NULL
            WHEN 'one_time_duration' THEN one_time_price_cents > 0 AND access_duration_days > 0
            WHEN 'subscription_monthly' THEN monthly_price_cents > 0
            WHEN 'subscription_yearly' THEN yearly_price_cents > 0
            ELSE FALSE
        END
        """
    )

    # Step 3: Restore default value to 'free'
    op.alter_column(
        'persona_pricing',
        'pricing_model',
        server_default='free'
    )

    # Note: We don't convert records back to 'free' because we don't know which ones were originally 'free'
