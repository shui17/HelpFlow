# 首次响应 SLA 运行指南

系统支持首次客服公开响应 SLA、提前提醒、超时升级、Redis 到期索引和数据库补偿。[设计与业务规则](../architecture/decisions/sla-scheduling.md)及 [OpenAPI](../api/helpflow.openapi.json)随代码交付。

## 升级和启动

从仓库根目录进入 backend，安装锁定依赖并迁移。升级业务库前先备份。

```powershell
cd backend
uv sync --locked
uv run alembic upgrade head
uv run alembic check
```

迁移版本为 `004_sla`，新增 `sla_rules`、`ticket_sla`、`sla_events`，回复时间升级为微秒精度。既有工单不补造历史 SLA 或通知，新建工单自动保存规则快照。回退004会删除 SLA 规则和历史结果，须先备份；下一层003对内部备注的回退保护继续生效。

默认规则：低24小时、普通8小时、高2小时、紧急1小时，提前15分钟提醒。按自然时间计算，UTC 存储；页面按浏览器本地时区显示。

在 `backend/.env` 中配置可选 Redis，前后端与扫描进程使用同一数据库。共享 Redis 的不同环境必须使用不同的待办键。

```dotenv
HELPFLOW_REDIS_URL=redis://127.0.0.1:6379/0
HELPFLOW_SLA_REDIS_KEY=helpflow:sla:pending
HELPFLOW_SLA_SCAN_SECONDS=5
HELPFLOW_SLA_COMPENSATE_SECONDS=60
HELPFLOW_SLA_BATCH_SIZE=100
```

按 README 启动前后端，再开一个终端持续运行扫描器。它是独立进程，不随 HTTP 服务自动启动。

```powershell
cd backend
uv run python -m scripts.scan_sla
```

没有 Redis 时留空 `HELPFLOW_REDIS_URL`，扫描器仍按补偿周期从数据库检测；正常工单提交、公开回复和关闭不依赖 Redis 可用。默认 Redis 模式每5秒扫描一次，数据库补偿默认每60秒执行；负载、锁等待和故障会增加延迟，不能将间隔当成精确送达承诺。未启动扫描器时，页面仍根据数据库时间显示逾期，提醒通知需等待扫描器启动或客服首次晚响应事务触发。

单轮扫描与恢复入口：

```powershell
uv run python -m scripts.scan_sla --once
uv run python -m scripts.scan_sla --rebuild
```

两者都执行一次数据库补偿并处理已到期业务。重建仅补齐数据库当前待办，不清空 Redis；过时成员读取后重查数据库并清理。进程在提交后、Redis 写入前退出，或 Redis 数据丢失时，下次补偿会找回待办。Redis 一轮连接失败后跳过后续索引写入，下一轮重新探测，避免每条待办重复等待连接超时。

发布规则时使用大于该优先级当前最大版本的整数，只影响后续新工单：

```powershell
uv run python -m scripts.configure_sla --priority high --version 2 --seconds 7200 --warning-seconds 900
```

第一版采用脚本管理，不提供规则管理页面。修改工单优先级、分配、转交、重新打开都不改变原快照。只有当时负责客服的第一次公开回复算响应，备注和用户回复不计；管理员没有公开回复入口。等于截止时间视为按时，大于截止时间视为超时，晚响应不会抹除升级记录。

取消或关闭未升级工单会终止等待；已经发生的升级保留。提醒和升级通知发送给当时启用的负责客服与管理员，未分配工单通知管理员。通知中的链接仍受当前工单权限限制。

## 接口和页面

现有工单响应新增可空 `sla`；空值表示没有历史快照。非空包含规则版本、创建时优先级、时限、提醒窗口、截止时间、首次响应、升级时间与状态。状态为 `waiting`、`due_soon`、`overdue`、`on_time`、`terminated`。

- `GET /api/v1/tickets?sla=due_soon|overdue`：与现有筛选、分页和角色权限共同生效。
- `GET /api/v1/tickets/summary`：counts 新增 due_soon、overdue；客服仍只统计本人负责工单。
- `GET /api/v1/tickets/{id}/sla-events`：经工单访问权限验证，返回提醒和升级记录，按 ID 升序。

首页新增 SLA 统计与筛选链接；列表新增响应时限筛选和状态；详情显示截止时间、首次响应、提醒与升级记录。已超时筛选也包含后来已回复或关闭的历史升级工单，便于复盘。页面通过刷新取得最新状态。

## 自动验证

沿用 README 的独立 `HELPFLOW_TEST_DATABASE_URL`，只允许 `helpflow_stage5_test` 前缀数据库。真实 Redis 用例额外要求显式 `HELPFLOW_TEST_REDIS_URL`，只操作随机生成的测试键，不执行 FLUSHDB。

```powershell
cd backend
# 在进程环境设置独立 MySQL 和 Redis 测试连接串
uv run pytest -q -rs
uv run python -m tests.seed_browser
cd ../frontend
npm test
npm run build
npm run test:e2e
```

SLA 测试覆盖微秒级截止前/恰好截止/截止后、重复回复、备注和用户补充、规则版本、历史无快照工单、改优先级与转交、重新打开与关闭、授权筛选、两个扫描器、扫描与回复/关闭竞争、跨批处理、通知失败和外层提交失败回滚、Redis 写入失败、断连及丢失后的补偿。

GitHub Actions 已配置 Redis 7 和 MySQL 服务，并设置真实 Redis 测试连接串；是否在远端通过以 Actions 实际结果为准。
