# 工单核心业务与活动时间线

> 历史设计记录：文中的实现范围反映当时版本；当前目录与依赖以 [文件职责图](../file-map.md) 为准。
依据阶段六交接、需求确认书及 docs/architecture/backend.md 的工单规则，按本次“进行阶段七的代码实现”指令实施，不创建 Git 提交。本阶段指学习路线的工单核心业务；PRD 中整体项目“阶段 7：Apifox 接口测试”是另一套阶段编号。

沿用 Router → Service → Repository → MySQL。与直接在路由中更新 ORM 相比，集中在 Service 中处理权限、业务规则和事务，便于 HTTP 与并发验证复用。同一事务内保存业务变更和 Activity，任一步失败全部回滚。无需新增表或迁移。

新增 POST /tickets/{id}/cancel、/claim、/assign 和 GET /tickets/{id}/activities。状态接口保留 PATCH，并增加总体设计中的 POST 别名。分配请求只有正整数 assignee_id；操作者始终来自当前登录用户。

领取仅允许启用客服，执行 WHERE id=:id AND status='open' AND assignee_id IS NULL 的条件 UPDATE，按 rowcount 判定；无此工单返回 404，已领取或状态变化返回 409。领取不改变 open 状态，设置 assigned_at，成功后只写一条 claimed 日志。失败者无需具备已领取工单的查看权限即可获得冲突提示，不返回工单详情。

管理员可以把未关闭工单分配给启用客服，首次分配写 assigned，替换写 reassigned。重复分配给当前负责人返回 409。分配与领取在工单更新前锁定目标客服用户行，与阶段六禁用/降级的用户行锁配合，避免账号变更与分配交错产生无效负责人。读取目标用户和锁定工单时刷新会话缓存。

撤销仅允许创建者操作 open 且无负责人的工单，设为 closed，设置 closed_at，写 cancelled。正常状态流转沿用阶段六角色和归属检查：负责客服 open → in_progress → resolved，创建者 resolved → in_progress 或 closed。分别记录 status_changed、reopened、closed；重新打开保留负责人。非法流转、关闭后的写入均被拒绝。

创建和主体修改分别写 created、updated。回复仍独立保存在 comments，刷新工单 updated_at，不混入活动时间线。工单响应补充 updated_at、assigned_at、closed_at。时间线只允许有权查看工单的人访问，按 created_at、id 升序，包含操作人、动作、状态及负责人前后值。

验证包括三角色完整 HTTP 流程、重新分配后旧客服失权、撤销、无效分配目标、重复操作、非法流转、关闭后写保护、不存在工单、时间线顺序与权限；真实 MySQL 两会话竞争领取必须一成功一冲突，仅一条领取日志；日志插入失败及提交失败必须回滚业务变更。保留阶段二至六回归，测试仅在显式隔离测试库上运行。

数据概览、前端和 Apifox 项目导入包不在本次工单核心业务范围，现有分类与查询接口保持原阶段行为。历史工单不会自动补造活动日志。
