"""RAG 知识库。"""
from alembic import op
import sqlalchemy as sa

revision = "005_knowledge"
down_revision = "004_sla"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("knowledge_documents",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("active_version", sa.Integer(), nullable=True))
    op.create_table("knowledge_versions",
        sa.Column("document_id", sa.String(100), sa.ForeignKey("knowledge_documents.id"), primary_key=True),
        sa.Column("version", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("digest", sa.String(64), nullable=False),
        sa.Column("embedding_space", sa.String(64), nullable=False))
    op.create_table("knowledge_chunks",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("document_id", sa.String(100), sa.ForeignKey("knowledge_documents.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("vector", sa.JSON(), nullable=False))
    op.create_index("ix_knowledge_chunks_document_id", "knowledge_chunks", ["document_id"])


def downgrade():
    op.drop_table("knowledge_chunks")
    op.drop_table("knowledge_versions")
    op.drop_table("knowledge_documents")
