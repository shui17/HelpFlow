# 演示数据

此步骤可选。先按 [项目首页](../../README.md) 安装依赖，单独创建 `helpflow_demo_local` 数据库，并将后端连接串指向该库，执行 `uv run alembic upgrade head` 后再初始化演示数据。普通部署不需要演示账号。


仅在 `helpflow_demo` 前缀的专用演示库运行：

```powershell
cd backend
uv run python -m scripts.seed_demo
```

脚本通过隐藏输入设置新建演示账号的共用密码，不重置既有密码，不覆盖既有工单。准备四个账号及待处理、处理中、已解决三种状态的示例工单：

| 角色 | 邮箱 |
| --- | --- |
| 普通用户 | `user@demo.example.com` |
| 客服一 | `agent1@demo.example.com` |
| 客服二 | `agent2@demo.example.com` |
| 管理员 | `admin@demo.example.com` |

也可用 `--password-env 环境变量名` 从进程环境读取密码，适用于自动化；不要把真实密码写入代码或提交到 Git。

完整演示：用户创建工单 → 客服领取 → 开始处理并回复 → 标记已解决 → 用户回复并确认关闭 → 管理员查看时间线、分配其它工单及管理用户。重新打开、撤销和并发领取冲突见 [工单指南](ticket-workflow.md)。
