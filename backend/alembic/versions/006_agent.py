"""Agent tasks, confirmation and transactional idempotency."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import DATETIME
revision = '006_agent'
down_revision = '005_knowledge'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('agent_tasks',
        sa.Column('id',sa.String(32),primary_key=True),
        sa.Column('user_id',sa.BigInteger(),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('ticket_id',sa.BigInteger(),sa.ForeignKey('tickets.id'),nullable=False),
        sa.Column('request_id',sa.String(64),nullable=False),
        sa.Column('mode',sa.String(20),nullable=False),
        sa.Column('instruction',sa.Text(),nullable=False),
        sa.Column('status',sa.String(32),nullable=False),
        sa.Column('fingerprint',sa.String(64),nullable=False),
        sa.Column('generation',sa.Integer(),nullable=False),
        sa.Column('lease_until',DATETIME(fsp=6)),
        sa.Column('rounds',sa.Integer(),nullable=False),
        sa.Column('tool_calls',sa.Integer(),nullable=False),
        sa.Column('proposal_version',sa.Integer(),nullable=False),
        sa.Column('content',sa.Text(),nullable=False),
        sa.Column('content_hash',sa.String(64),nullable=False),
        sa.Column('sources',sa.JSON(),nullable=False),
        sa.Column('trace',sa.JSON(),nullable=False),
        sa.Column('expires_at',DATETIME(fsp=6)),
        sa.Column('result_id',sa.BigInteger(),sa.ForeignKey('ticket_comments.id')),
        sa.Column('error',sa.String(300)),
        sa.Column('created_at',DATETIME(fsp=6),nullable=False),
        sa.UniqueConstraint('user_id','request_id',name='uq_agent_user_request'))
    op.create_index('ix_agent_user_ticket_created','agent_tasks',['user_id','ticket_id','created_at'])
    op.create_table('agent_executions',
        sa.Column('task_id',sa.String(32),sa.ForeignKey('agent_tasks.id'),primary_key=True),
        sa.Column('proposal_version',sa.Integer(),primary_key=True),
        sa.Column('content_hash',sa.String(64),nullable=False),
        sa.Column('comment_id',sa.BigInteger(),sa.ForeignKey('ticket_comments.id'),nullable=False),
        sa.Column('created_at',DATETIME(fsp=6),nullable=False))


def downgrade():
    op.drop_table('agent_executions')
    op.drop_table('agent_tasks')
