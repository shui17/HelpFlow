"""增加工单更新时间；用于升级、回退、重新升级练习。"""
from alembic import op
import sqlalchemy as sa

revision = "002_ticket_updated_at"
down_revision = "001_five_tables"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("tickets", sa.Column("updated_at", sa.DateTime(), nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")))


def downgrade():
    op.drop_column("tickets", "updated_at")
