USE helpflow_stage4;
SET NAMES utf8mb4;
SET time_zone = '+00:00';
SET @creator_id = 1, @agent_id = 3, @ticket_id = 2;

-- 1. 用户工单列表；相同时间用 ID 打破平局，第一页最多 10 条。
SELECT id, ticket_no, title, priority, status, created_at
FROM tickets WHERE creator_id = @creator_id
ORDER BY created_at DESC, id DESC LIMIT 10 OFFSET 0;
SELECT COUNT(*) AS total FROM tickets WHERE creator_id = @creator_id;

-- 2. 待领取：NULL 不能用 = NULL 判断。
SELECT id, ticket_no, title, priority FROM tickets
WHERE status = 'open' AND assignee_id IS NULL ORDER BY created_at, id;

-- 3. 客服正在处理的工单。
SELECT id, title, status FROM tickets
WHERE assignee_id = @agent_id AND status = 'in_progress'
ORDER BY created_at DESC, id DESC;

-- 4. 状态统计；只返回有数据的分组。
SELECT status, COUNT(*) AS total FROM tickets GROUP BY status ORDER BY status;

-- 5. HAVING 筛选分组统计结果，WHERE 筛选参与统计的原始行。
SELECT creator_id, COUNT(*) AS total FROM tickets
WHERE status <> 'closed' GROUP BY creator_id HAVING COUNT(*) >= 2;

-- 6. 创建人必定存在，负责人可以为空：分别使用 INNER JOIN 和 LEFT JOIN。
SELECT t.id, t.title, creator.username AS creator_name, agent.username AS assignee_name
FROM tickets AS t
JOIN users AS creator ON creator.id = t.creator_id
LEFT JOIN users AS agent ON agent.id = t.assignee_id ORDER BY t.id;

-- 7. 回复与活动时间线分开查询，避免 JOIN 两个一对多集合导致行数相乘。
SELECT c.id, u.username, c.content, c.created_at FROM ticket_comments AS c
JOIN users AS u ON u.id = c.author_id
WHERE c.ticket_id = @ticket_id ORDER BY c.created_at, c.id;
SELECT a.id, a.action, u.username AS operator_name, a.old_status, a.new_status,
       a.description, a.created_at
FROM ticket_activity_logs AS a JOIN users AS u ON u.id = a.operator_id
WHERE a.ticket_id = @ticket_id ORDER BY a.created_at, a.id;

-- 8. 搜索和筛选。应用接入时使用绑定参数，不拼接客户端字符串。
SELECT id, title, priority FROM tickets
WHERE creator_id = @creator_id AND priority IN ('high', 'urgent')
  AND (title LIKE '%支付%' OR ticket_no = 'HF-DEMO-001')
ORDER BY created_at DESC, id DESC;

-- 9. 管理员操作记录。
SELECT l.id, target.username AS target_name, operator.username AS operator_name,
       l.action, l.old_is_active, l.new_is_active
FROM user_admin_logs AS l
JOIN users AS target ON target.id = l.target_user_id
JOIN users AS operator ON operator.id = l.operator_id
WHERE l.target_user_id = 5 ORDER BY l.created_at, l.id;
