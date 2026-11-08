# 测试与验证

从仓库根目录执行：


```powershell
cd backend
uv run pytest -q
cd ../frontend
npm test
npm run build
```

默认跳过真实 MySQL 测试。运行全量测试时必须使用独立测试库，库名以 `helpflow_stage5_test` 开头，连接串通过进程变量 `HELPFLOW_TEST_DATABASE_URL` 提供。测试会迁移及回退测试库字段，不能指向业务库或演示库。详情见 [数据库指南](database.md)。


真实 Redis 用例还需显式设置 `HELPFLOW_TEST_REDIS_URL`；未提供服务配置的集成测试会跳过，应检查 pytest 的跳过原因，不能将跳过视为通过。

## 浏览器回归

先在 `backend` 进程环境设置独立的 `HELPFLOW_TEST_DATABASE_URL`，执行全量 `uv run pytest -q`（会迁移测试库），再准备测试账号并启动浏览器回归：

```powershell
# 在 backend 执行，沿用上面设置的独立测试库环境变量
uv run python -m tests.seed_browser
cd ../frontend
npx playwright install chromium
npm run test:e2e
```

测试使用专用端口 8011 和 5175，自动启动、关闭前后端，验证用户注册和创建工单、客服领取回复与解决、用户确认关闭、管理员查看，以及服务端临时 503 后保留会话并恢复。测试启动前校验测试库前缀，强制后端使用该测试库，不使用业务库连接。浏览器测试账号只在测试库创建，默认密码 `BrowserTest123`，可用 `E2E_PASSWORD` 覆盖；已有测试账号不重置密码。可选 `E2E_BROWSER_PATH` 指定本机 Chromium 浏览器路径。


## 持续集成

[GitHub Actions](../../.github/workflows/ci.yml) 配置独立 MySQL 和 Redis 服务，执行后端测试、前端测试、生产构建及浏览器回归。验证状态以本次测试输出及对应提交的 CI 结果为准。

## 性能与调度测量

在 backend 目录配置独立测试库后，运行 `uv run python -m scripts.benchmark_summary` 或 `uv run python -m scripts.measure_sla`。默认报告分别写入仓库根目录下的 `.local/summary-measurement.json` 和 `.local/sla-measurement.json`，不进入文档目录。可用 `--output` 指定其他位置，目录不存在时自动创建。SLA 测量未配置真实 Redis 时仅验证数据库补偿路径。
