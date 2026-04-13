"""add_text_search_tsv_to_embeddings

Revision ID: 658aed2d84a4
Revises: 5ba7eefcbec1
Create Date: 2025-10-13 20:29:35.131462

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '658aed2d84a4'
down_revision: Union[str, Sequence[str], None] = '5ba7eefcbec1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add full-text search column to embeddings table (idempotent)."""

    # Add tsvector column for full-text search (IF NOT EXISTS)
    op.execute("""
        ALTER TABLE data_llamaindex_embeddings
        ADD COLUMN IF NOT EXISTS text_search_tsv tsvector
    """)

    # Create GIN index for fast full-text search (IF NOT EXISTS)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_embeddings_text_search
        ON data_llamaindex_embeddings
        USING gin(text_search_tsv)
    """)

    # Create trigger function to automatically update tsvector when text changes
    # (CREATE OR REPLACE is already idempotent)
    op.execute("""
        CREATE OR REPLACE FUNCTION embeddings_text_search_trigger() RETURNS trigger AS $$
        BEGIN
            NEW.text_search_tsv := to_tsvector('english', COALESCE(NEW.text, ''));
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)

    # Create trigger on INSERT and UPDATE (drop first if exists to be safe)
    op.execute("""
        DROP TRIGGER IF EXISTS trig_embeddings_text_search_update ON data_llamaindex_embeddings
    """)
    op.execute("""
        CREATE TRIGGER trig_embeddings_text_search_update
        BEFORE INSERT OR UPDATE OF text
        ON data_llamaindex_embeddings
        FOR EACH ROW
        EXECUTE FUNCTION embeddings_text_search_trigger()
    """)

    # Backfill existing rows (only update NULL values to avoid unnecessary work)
    print("Backfilling text_search_tsv for existing embeddings...")
    op.execute("""
        UPDATE data_llamaindex_embeddings
        SET text_search_tsv = to_tsvector('english', COALESCE(text, ''))
        WHERE text_search_tsv IS NULL
    """)


def downgrade() -> None:
    """Remove full-text search column from embeddings table."""

    # Drop trigger
    op.execute("DROP TRIGGER IF EXISTS trig_embeddings_text_search_update ON data_llamaindex_embeddings")

    # Drop trigger function
    op.execute("DROP FUNCTION IF EXISTS embeddings_text_search_trigger()")

    # Drop index
    op.execute("DROP INDEX IF EXISTS idx_embeddings_text_search")

    # Drop column
    op.execute("ALTER TABLE data_llamaindex_embeddings DROP COLUMN IF EXISTS text_search_tsv")
