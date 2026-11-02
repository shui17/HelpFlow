-- 使用 mysql 客户端批处理执行；需要 CREATE ROUTINE / ALTER ROUTINE / EXECUTE 权限。
-- 每次运行新增一张独立的演示工单和一条创建记录，不修改种子工单。
USE helpflow_stage4;
SET NAMES utf8mb4;
SET time_zone = '+00:00';
DROP PROCEDURE IF EXISTS stage4_transaction_demo;
DELIMITER $$
CREATE PROCEDURE stage4_transaction_demo()
BEGIN
    DECLARE demo_id BIGINT;
    DECLARE duplicate_caught BOOLEAN DEFAULT FALSE;
    DECLARE status_after VARCHAR(20);
    DECLARE logs_after INT;
    -- 非预期错误必须回滚并抛出，不能被演示吞掉。
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;
    INSERT INTO tickets (ticket_no, title, description, category, creator_id)
    VALUES (REPLACE(UUID(), '-', ''), '事务演示', '创建与活动记录同时提交', 'other', 1);
    SET demo_id = LAST_INSERT_ID();
    INSERT INTO ticket_activity_logs (ticket_id, action, operator_id, new_status, description)
    VALUES (demo_id, 'created', 1, 'open', '事务提交演示');
    COMMIT;
    SELECT 'commit' AS scenario, id, status FROM tickets WHERE id = demo_id;

    BEGIN
        -- 唯一约束只撤销失败语句，不自动撤销前面的 UPDATE；这里显式回滚整个事务。
        DECLARE EXIT HANDLER FOR 1062
        BEGIN
            ROLLBACK;
            SET duplicate_caught = TRUE;
        END;
        START TRANSACTION;
        UPDATE tickets SET status = 'in_progress', assignee_id = 3,
            assigned_at = UTC_TIMESTAMP() WHERE id = demo_id;
        INSERT INTO ticket_activity_logs
            (ticket_id, action, operator_id, old_status, new_status, new_assignee_id)
        VALUES (demo_id, 'claimed', 3, 'open', 'in_progress', 3);
        -- 种子邮箱已存在，真实触发 1062 错误。
        INSERT INTO users (username, email, password_hash)
        VALUES ('重复邮箱', 'lin@example.test', '!stage4-no-login');
        -- 如果没有触发预期错误，也不能提交本次修改。
        ROLLBACK;
    END;

    SELECT status INTO status_after FROM tickets WHERE id = demo_id;
    SELECT COUNT(*) INTO logs_after FROM ticket_activity_logs WHERE ticket_id = demo_id;
    IF NOT duplicate_caught OR status_after <> 'open' OR logs_after <> 1
       OR EXISTS (SELECT 1 FROM tickets WHERE id = demo_id AND
                  (assignee_id IS NOT NULL OR assigned_at IS NOT NULL)) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Transaction rollback verification failed';
    END IF;
    SELECT 'rollback' AS scenario, duplicate_caught AS expected_error_caught,
           status_after AS status_after_rollback, logs_after AS logs_after_rollback,
           'PASS' AS result;
END$$
DELIMITER ;
CALL stage4_transaction_demo();
DROP PROCEDURE stage4_transaction_demo;
