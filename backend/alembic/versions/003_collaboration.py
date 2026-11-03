"""客服协作与事务内通知；既有回复保持公开。"""
from alembic import op
import sqlalchemy as sa

revision = "003_collaboration"
down_revision = "002_ticket_updated_at"
branch_labels = None
depends_on = None

OLD_ACTIONS = "'created', 'updated', 'cancelled', 'claimed', 'assigned', 'reassigned', 'status_changed', 'reopened', 'closed'"


def upgrade():
    op.add_column("ticket_comments", sa.Column("visibility", sa.String(20), nullable=False, server_default="public"))
    op.create_check_constraint("ck_comments_visibility", "ticket_comments", "visibility IN ('public', 'internal')")
    op.create_index("ix_comments_visibility_id", "ticket_comments", ["ticket_id", "visibility", "id"])
    op.drop_constraint("ck_activity_action", "ticket_activity_logs", type_="check")
    op.create_check_constraint("ck_activity_action", "ticket_activity_logs", f"action IN ({OLD_ACTIONS}, 'transferred')")
    op.create_table("notifications",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("recipient_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("ticket_id", sa.BigInteger(), sa.ForeignKey("tickets.id"), nullable=False),
        sa.Column("event_key", sa.String(80), nullable=False),
        sa.Column("message", sa.String(200), nullable=False),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("event_key", "recipient_id", name="uq_notifications_event_recipient"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci")
    op.create_index("ix_notifications_recipient_id", "notifications", ["recipient_id", "id"])
    op.create_index("ix_notifications_recipient_read", "notifications", ["recipient_id", "read_at", "id"])
    op.create_index("ix_notifications_ticket", "notifications", ["ticket_id"])


def downgrade():
    connection = op.get_bind()
    if connection.scalar(sa.text("SELECT COUNT(*) FROM ticket_comments WHERE visibility='internal'")):
        raise RuntimeError("存在内部备注，不能回退为不支持可见性的版本；请先备份并处理内部备注")
    # 转交历史保留为重新分配，原因仍在 description 中。
    op.execute("UPDATE ticket_activity_logs SET action='reassigned' WHERE action='transferred'")
    op.drop_constraint("ck_activity_action", "ticket_activity_logs", type_="check")
    op.create_check_constraint("ck_activity_action", "ticket_activity_logs", f"action IN ({OLD_ACTIONS})")
    op.drop_table("notifications")
    # 不把内部备注降级成公开回复；有内部数据时拒绝有损回退。
    op.drop_index("ix_comments_visibility_id", table_name="ticket_comments")
    op.drop_constraint("ck_comments_visibility", "ticket_comments", type_="check")
    op.drop_column("ticket_comments", "visibility")
