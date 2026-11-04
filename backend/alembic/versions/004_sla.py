"""首次响应 SLA；历史工单不追溯补发。"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import DATETIME

revision = "004_sla"
down_revision = "003_collaboration"
branch_labels = None
depends_on = None
OPTIONS = dict(mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci")


def upgrade():
    op.alter_column("ticket_comments", "created_at", existing_type=sa.DateTime(),
                    type_=DATETIME(fsp=6), existing_nullable=False,
                    server_default=sa.text("CURRENT_TIMESTAMP(6)"))
    rules = op.create_table("sla_rules",
        sa.Column("priority", sa.String(20), primary_key=True),
        sa.Column("version", sa.Integer(), primary_key=True),
        sa.Column("response_seconds", sa.Integer(), nullable=False),
        sa.Column("warning_seconds", sa.Integer(), nullable=False),
        sa.CheckConstraint("response_seconds > 0 AND warning_seconds >= 0 AND warning_seconds < response_seconds", name="ck_sla_rule_duration"),
        sa.CheckConstraint("version > 0", name="ck_sla_rule_version"),
        sa.CheckConstraint("priority IN ('low', 'normal', 'high', 'urgent')", name="ck_sla_rule_priority"), **OPTIONS)
    op.bulk_insert(rules, [dict(priority=p, version=1, response_seconds=h*3600, warning_seconds=900)
                         for p, h in [("low", 24), ("normal", 8), ("high", 2), ("urgent", 1)]])
    op.create_table("ticket_sla",
        sa.Column("ticket_id", sa.BigInteger(), sa.ForeignKey("tickets.id"), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("priority", sa.String(20), nullable=False),
        sa.Column("response_seconds", sa.Integer(), nullable=False),
        sa.Column("warning_seconds", sa.Integer(), nullable=False),
        sa.Column("started_at", DATETIME(fsp=6), nullable=False),
        sa.Column("due_at", DATETIME(fsp=6), nullable=False),
        sa.Column("first_response_at", DATETIME(fsp=6)),
        sa.Column("terminated_at", DATETIME(fsp=6)),
        sa.Column("escalated_at", DATETIME(fsp=6)), **OPTIONS)
    op.create_index("ix_sla_pending_due", "ticket_sla",
                    ["first_response_at", "terminated_at", "escalated_at", "due_at", "ticket_id"])
    op.create_table("sla_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("ticket_id", sa.BigInteger(), sa.ForeignKey("tickets.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("occurred_at", DATETIME(fsp=6), nullable=False),
        sa.Column("due_at", DATETIME(fsp=6), nullable=False),
        sa.UniqueConstraint("ticket_id", "version", "kind", name="uq_sla_event"),
        sa.CheckConstraint("kind IN ('due_soon', 'overdue')", name="ck_sla_event_kind"), **OPTIONS)


def downgrade():
    op.drop_table("sla_events")
    op.drop_table("ticket_sla")
    op.drop_table("sla_rules")
    op.alter_column("ticket_comments", "created_at", existing_type=DATETIME(fsp=6),
                    type_=sa.DateTime(), existing_nullable=False,
                    server_default=sa.text("CURRENT_TIMESTAMP"))
