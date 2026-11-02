# HelpFlow 练习空文件结构设计

> 历史设计记录：文中的实现范围反映当时版本；当前目录与依赖以 [文件职责图](../file-map.md) 为准。
## 目标

为阶段一 Python 项目基础练习建立独立包结构。此步骤只创建目录和空 Python 文件，不编写实现代码，不修改现有 FastAPI 应用。

## 目录结构

```text
backend/
└── practice/
    ├── __init__.py
    └── stage1_helpflow/
        ├── __init__.py
        ├── enums.py
        ├── models.py
        ├── exceptions.py
        ├── storage.py
        ├── services.py
        ├── logging_config.py
        └── main.py
```

## 文件职责

- `practice/__init__.py`：声明练习代码包。
- `stage1_helpflow/__init__.py`：声明阶段一练习子包。
- `enums.py`：后续定义角色、工单状态和优先级枚举。
- `models.py`：后续定义 `User`、`Ticket` 和 `Comment` 数据类。
- `exceptions.py`：后续定义业务异常。
- `storage.py`：后续实现内存存储。
- `services.py`：后续实现工单业务规则。
- `logging_config.py`：后续配置基础日志。
- `main.py`：后续作为命令行练习入口。

## 实施边界

- 所有目标文件保持完全为空。
- 不修改 `backend/app/main.py`。
- 不增加第三方依赖。
- 不建立 FastAPI 路由、数据库代码或测试代码。
- 正式项目不依赖 `practice` 包；后续只选择性迁移有价值的实现。

## 验证

- 检查全部目录和文件均已创建。
- 检查目标文件长度均为零字节。
- 检查 `backend/app/main.py` 未发生变化。
