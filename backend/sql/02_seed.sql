-- 首次空表导入；重复导入会报主键冲突。不要使用 --force 忽略错误。
USE helpflow_stage4;
SET NAMES utf8mb4;
SET time_zone = '+00:00';
START TRANSACTION;

-- 明确无效的哈希占位值，仅供 SQL 学习，不能用于登录。
INSERT INTO users (id, username, email, password_hash, role, is_active) VALUES
    (1, '小林', 'lin@example.test', '!stage4-no-login', 'user', TRUE),
    (2, '小周', 'zhou@example.test', '!stage4-no-login', 'user', TRUE),
    (3, '客服陈', 'agent@example.test', '!stage4-no-login', 'agent', TRUE),
    (4, '管理员', 'admin@example.test', '!stage4-no-login', 'admin', TRUE),
    (5, '停用用户', 'disabled@example.test', '!stage4-no-login', 'user', FALSE);

INSERT INTO tickets
    (id, ticket_no, title, description, category, priority, status, creator_id,
     assignee_id, assigned_at, closed_at, created_at, updated_at) VALUES
    (1, 'HF-DEMO-001', '无法登录账号', '输入账号后出现错误。', 'account', 'high', 'open', 1,
     NULL, NULL, NULL, '2026-11-01 08:00:00', '2026-11-01 08:00:00'),
    (2, 'HF-DEMO-002', '支付结果未更新', '付款后仍显示待支付。', 'payment', 'urgent', 'in_progress', 1,
     3, '2026-11-01 09:10:00', NULL, '2026-11-01 09:00:00', '2026-11-01 09:10:00'),
    (3, 'HF-DEMO-003', '产品使用咨询', '如何修改个人设置？', 'product', 'normal', 'resolved', 2,
     3, '2026-11-01 10:10:00', NULL, '2026-11-01 10:00:00', '2026-11-01 10:20:00'),
    (4, 'HF-DEMO-004', '页面加载失败', '访问页面时显示空白。', 'technical', 'high', 'closed', 2,
     3, '2026-11-01 11:10:00', '2026-11-01 11:30:00', '2026-11-01 11:00:00', '2026-11-01 11:30:00'),
    (5, 'HF-DEMO-005', '其他问题咨询', '想了解服务时间。', 'other', 'low', 'open', 2,
     NULL, NULL, NULL, '2026-11-01 12:00:00', '2026-11-01 12:00:00');

INSERT INTO ticket_comments (ticket_id, author_id, content, created_at) VALUES
    (2, 1, '已经支付成功，请协助核实。', '2026-11-01 09:11:00'),
    (2, 3, '正在核对支付记录。', '2026-11-01 09:12:00'),
    (3, 3, '请前往个人设置页面修改。', '2026-11-01 10:19:00');

INSERT INTO ticket_activity_logs (ticket_id, action, operator_id, new_status, description, created_at)
SELECT id, 'created', creator_id, 'open', '创建工单', created_at FROM tickets;

INSERT INTO ticket_activity_logs
    (ticket_id, action, operator_id, old_status, new_status, new_assignee_id, description, created_at)
SELECT id, 'claimed', 3, 'open', 'in_progress', 3, '客服领取', assigned_at
FROM tickets WHERE id IN (2, 3, 4);

INSERT INTO ticket_activity_logs
    (ticket_id, action, operator_id, old_status, new_status, description, created_at) VALUES
    (3, 'status_changed', 3, 'in_progress', 'resolved', '已提供解决方案', '2026-11-01 10:20:00'),
    (4, 'status_changed', 3, 'in_progress', 'resolved', '页面已修复', '2026-11-01 11:20:00'),
    (4, 'closed', 2, 'resolved', 'closed', '用户确认关闭', '2026-11-01 11:30:00');

INSERT INTO user_admin_logs (target_user_id, operator_id, action, old_is_active, new_is_active)
VALUES (5, 4, 'account_disabled', TRUE, FALSE);
COMMIT;

SELECT 'users' AS table_name, COUNT(*) AS row_count FROM users
UNION ALL SELECT 'tickets', COUNT(*) FROM tickets
UNION ALL SELECT 'ticket_comments', COUNT(*) FROM ticket_comments
UNION ALL SELECT 'ticket_activity_logs', COUNT(*) FROM ticket_activity_logs
UNION ALL SELECT 'user_admin_logs', COUNT(*) FROM user_admin_logs;
