# 数据库配置与迁移

应用使用 MySQL，连接串由 `HELPFLOW_DATABASE_URL` 提供，驱动为 `mysql+asyncmy`。建库、依赖安装和环境变量配置见 [项目首页](../../README.md)。业务时间使用 UTC。

## 迁移

升级已有业务库前先备份。从仓库根目录执行：

```powershell
cd backend
uv sync --locked
uv run alembic upgrade head
uv run alembic current
uv run alembic check
```

迁移历史位于 `backend/alembic/versions`，依次包含基础五表、工单更新时间、客服协作与通知、SLA 规则与记录。应用数据库通过 Alembic 管理，不使用独立 SQL 练习脚本初始化，不通过删除表替代迁移。

回退可能删除字段和业务记录。协作迁移包含内部备注回退保护，SLA 回退会删除规则和历史结果，具体见 [协作指南](collaboration.md) 与 [SLA 指南](sla.md)。

## 数据隔离

- 普通应用库：通过 `HELPFLOW_DATABASE_URL` 配置。
- 演示库：库名必须以 `helpflow_demo` 开头，见 [演示初始化](demo-data.md)。
- 测试库：显式设置 `HELPFLOW_TEST_DATABASE_URL`，库名必须以 `helpflow_stage5_test` 开头。该前缀是代码中的安全约束，不能仅修改文档中的名称。

测试会执行迁移、回退和数据写入；迁移测试还会创建并删除随机命名的专用测试库，测试账号需有相应权限。不得指向业务库或演示库。完整命令见 [测试指南](verification.md)。
