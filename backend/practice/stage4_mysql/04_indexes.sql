USE helpflow_stage4;
SHOW INDEX FROM users;
SHOW INDEX FROM tickets;
SHOW INDEX FROM ticket_activity_logs;

-- possible_keys 是候选，key 是实际使用的索引，rows 是估算值。
-- 小数据集可能全表扫描；不使用 FORCE INDEX 伪造优化效果。
EXPLAIN SELECT id FROM users WHERE email = 'lin@example.test';
EXPLAIN SELECT id, title FROM tickets WHERE creator_id = 1
ORDER BY created_at DESC, id DESC LIMIT 10;

-- 联合索引 (assignee_id, status, created_at, id) 的左侧两列为等值条件。
EXPLAIN SELECT id, title FROM tickets
WHERE assignee_id = 3 AND status = 'in_progress'
ORDER BY created_at DESC, id DESC LIMIT 10;

-- 省略左侧 assignee_id 时，不能简单认定仍可高效定位联合索引。
EXPLAIN SELECT id, title FROM tickets WHERE status = 'in_progress';

-- 普通 B-tree 索引通常不能对前导通配符进行范围定位。
EXPLAIN SELECT id, title FROM tickets WHERE title LIKE '%支付%';
EXPLAIN SELECT id, action FROM ticket_activity_logs WHERE ticket_id = 2
ORDER BY created_at, id;
