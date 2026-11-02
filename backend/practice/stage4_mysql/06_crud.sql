USE helpflow_stage4;
SET NAMES utf8mb4;
SET time_zone = '+00:00';
-- 使用临时表练习 DELETE / ALTER，不删除用户、工单或审计日志。
CREATE TEMPORARY TABLE stage4_crud_notes (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    content VARCHAR(100) NOT NULL
) ENGINE=InnoDB;
-- DDL 与 DML 事务分开；ALTER TABLE 会造成隐式提交。
ALTER TABLE stage4_crud_notes ADD COLUMN label VARCHAR(20) NULL;
START TRANSACTION;
INSERT INTO stage4_crud_notes (content, label) VALUES ('原始内容', 'practice');
SET @note_id = LAST_INSERT_ID();
SELECT * FROM stage4_crud_notes WHERE id = @note_id;
UPDATE stage4_crud_notes SET content = '修改后的内容' WHERE id = @note_id;
SELECT * FROM stage4_crud_notes WHERE id = @note_id;
DELETE FROM stage4_crud_notes WHERE id = @note_id;
SELECT COUNT(*) AS rows_after_delete FROM stage4_crud_notes;
ROLLBACK;
SELECT COUNT(*) AS rows_after_rollback FROM stage4_crud_notes;
DROP TEMPORARY TABLE stage4_crud_notes;
