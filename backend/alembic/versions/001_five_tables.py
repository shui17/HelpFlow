"""阶段五基线五表；冻结阶段四 SQL，tickets.updated_at 由下一迁移添加。"""
from alembic import op

revision = "001_five_tables"
down_revision = None
branch_labels = None
depends_on = None

# 迁移自包含，不读取未来可能改变的 ORM 或练习 SQL 文件。
STATEMENTS = [
    """CREATE TABLE users (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(30) NOT NULL,
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'user',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_users_email UNIQUE (email),
    CONSTRAINT ck_users_role CHECK (role IN ('user', 'agent', 'admin')),
    CONSTRAINT ck_users_active CHECK (is_active IN (0, 1)),
    INDEX ix_users_role (role),
    INDEX ix_users_active (is_active)
) ENGINE=InnoDB""",
    """CREATE TABLE tickets (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    ticket_no VARCHAR(32) NOT NULL,
    title VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    category VARCHAR(20) NOT NULL,
    priority VARCHAR(20) NOT NULL DEFAULT 'normal',
    status VARCHAR(20) NOT NULL DEFAULT 'open',
    creator_id BIGINT NOT NULL,
    assignee_id BIGINT NULL,
    assigned_at DATETIME NULL,
    closed_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_tickets_no UNIQUE (ticket_no),
    CONSTRAINT fk_tickets_creator FOREIGN KEY (creator_id) REFERENCES users(id),
    CONSTRAINT fk_tickets_assignee FOREIGN KEY (assignee_id) REFERENCES users(id),
    CONSTRAINT ck_tickets_category CHECK (category IN ('account', 'product', 'payment', 'technical', 'other')),
    CONSTRAINT ck_tickets_priority CHECK (priority IN ('low', 'normal', 'high', 'urgent')),
    CONSTRAINT ck_tickets_status CHECK (status IN ('open', 'in_progress', 'resolved', 'closed')),
    INDEX ix_tickets_creator_created (creator_id, created_at, id),
    INDEX ix_tickets_assignee_status_created (assignee_id, status, created_at, id),
    INDEX ix_tickets_status (status),
    INDEX ix_tickets_priority (priority),
    INDEX ix_tickets_category (category),
    INDEX ix_tickets_created (created_at)
) ENGINE=InnoDB""",
    """CREATE TABLE ticket_comments (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    ticket_id BIGINT NOT NULL,
    author_id BIGINT NOT NULL,
    content TEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_comments_ticket FOREIGN KEY (ticket_id) REFERENCES tickets(id),
    CONSTRAINT fk_comments_author FOREIGN KEY (author_id) REFERENCES users(id),
    CONSTRAINT ck_comments_content CHECK (CHAR_LENGTH(TRIM(content)) BETWEEN 1 AND 2000),
    INDEX ix_comments_ticket_created (ticket_id, created_at, id),
    INDEX ix_comments_author (author_id)
) ENGINE=InnoDB""",
    """CREATE TABLE ticket_activity_logs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    ticket_id BIGINT NOT NULL,
    action VARCHAR(30) NOT NULL,
    operator_id BIGINT NOT NULL,
    old_status VARCHAR(20) NULL,
    new_status VARCHAR(20) NULL,
    old_assignee_id BIGINT NULL,
    new_assignee_id BIGINT NULL,
    description VARCHAR(500) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_activity_ticket FOREIGN KEY (ticket_id) REFERENCES tickets(id),
    CONSTRAINT fk_activity_operator FOREIGN KEY (operator_id) REFERENCES users(id),
    CONSTRAINT fk_activity_old_assignee FOREIGN KEY (old_assignee_id) REFERENCES users(id),
    CONSTRAINT fk_activity_new_assignee FOREIGN KEY (new_assignee_id) REFERENCES users(id),
    CONSTRAINT ck_activity_action CHECK (action IN ('created', 'updated', 'cancelled', 'claimed', 'assigned', 'reassigned', 'status_changed', 'reopened', 'closed')),
    CONSTRAINT ck_activity_old_status CHECK (old_status IN ('open', 'in_progress', 'resolved', 'closed')),
    CONSTRAINT ck_activity_new_status CHECK (new_status IN ('open', 'in_progress', 'resolved', 'closed')),
    INDEX ix_activity_ticket_created (ticket_id, created_at, id),
    INDEX ix_activity_operator (operator_id),
    INDEX ix_activity_old_assignee (old_assignee_id),
    INDEX ix_activity_new_assignee (new_assignee_id),
    INDEX ix_activity_action (action)
) ENGINE=InnoDB""",
    """CREATE TABLE user_admin_logs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    target_user_id BIGINT NOT NULL,
    operator_id BIGINT NOT NULL,
    action VARCHAR(30) NOT NULL,
    old_role VARCHAR(20) NULL,
    new_role VARCHAR(20) NULL,
    old_is_active BOOLEAN NULL,
    new_is_active BOOLEAN NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_admin_target FOREIGN KEY (target_user_id) REFERENCES users(id),
    CONSTRAINT fk_admin_operator FOREIGN KEY (operator_id) REFERENCES users(id),
    CONSTRAINT ck_admin_action CHECK (action IN ('role_changed', 'account_enabled', 'account_disabled')),
    CONSTRAINT ck_admin_old_role CHECK (old_role IN ('user', 'agent', 'admin')),
    CONSTRAINT ck_admin_new_role CHECK (new_role IN ('user', 'agent', 'admin')),
    CONSTRAINT ck_admin_old_active CHECK (old_is_active IN (0, 1)),
    CONSTRAINT ck_admin_new_active CHECK (new_is_active IN (0, 1)),
    INDEX ix_admin_target_created (target_user_id, created_at, id),
    INDEX ix_admin_operator (operator_id),
    INDEX ix_admin_action (action)
) ENGINE=InnoDB"""
]


def upgrade():
    for statement in STATEMENTS:
        op.execute(statement)


def downgrade():
    op.drop_table("user_admin_logs")
    op.drop_table("ticket_activity_logs")
    op.drop_table("ticket_comments")
    op.drop_table("tickets")
    op.drop_table("users")
