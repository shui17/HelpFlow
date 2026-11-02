# HelpFlow 剩余代码设计

> 历史设计记录：文中的实现范围反映当时版本；当前目录与依赖以 [文件职责图](../file-map.md) 为准。
## 1. 目标

补齐阶段 2 尚未实现的两类代码：

1. REST 集合资源的筛选与分页；
2. Python `asyncio` 的串行等待、Task、`gather` 和阻塞函数处理练习。

本次实现继续使用阶段 1 的内存存储，不提前引入登录、JWT、MySQL、SQLAlchemy 或 Vue。

## 2. 工单列表接口

新增接口：

```http
GET /api/v1/tickets?page=1&page_size=10&status=open&priority=high
```

查询参数：

- `page`：页码，默认 `1`，最小 `1`；
- `page_size`：每页数量，默认 `10`，最小 `1`，最大 `100`；
- `status`：可选工单状态筛选；
- `priority`：可选工单优先级筛选。

返回数据：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [],
    "page": 1,
    "page_size": 10,
    "total": 0
  }
}
```

`total` 表示筛选后、分页前的记录总数。列表按照工单 ID 倒序排列，使新创建的工单排在前面。超出数据范围的页返回空 `items`，不视为错误。

## 3. 分层职责

### 3.1 Storage

`MemoryStorage.list_tickets()` 只负责返回当前全部工单，不理解 HTTP 查询参数，也不负责业务筛选。

### 3.2 Service

`TicketService.list_tickets()` 负责：

- 按状态筛选；
- 按优先级筛选；
- 按 ID 倒序排列；
- 计算筛选后的总数；
- 根据 `page` 和 `page_size` 切片。

方法返回当前页工单列表和总数。

### 3.3 Router 与 Schema

Router 使用 FastAPI `Query` 声明参数范围。非法页码、非法页大小和非法枚举由 FastAPI/Pydantic 在进入 Service 之前转换为 HTTP `422`。

Schema 新增通用 `PageData[T]`，表示分页数据结构。

## 4. 异步练习

新增目录：

```text
backend/practice/stage2_async/
├── __init__.py
└── async_demo.py
```

`async_demo.py` 包含：

- `simulate_io()`：使用 `await asyncio.sleep()` 模拟网络或数据库等待；
- `run_serial()`：依次等待多个操作；
- `run_with_tasks()`：通过 `asyncio.create_task()` 创建 Task；
- `run_with_gather()`：通过 `asyncio.gather()` 并发等待；
- `run_blocking_safely()`：通过 `asyncio.to_thread()` 将阻塞函数放到线程中执行；
- `main()`：依次运行示例，打印结果和耗时。

练习脚本不会在协程中直接调用 `time.sleep()`。`time.sleep()` 只存在于普通同步函数中，并由 `asyncio.to_thread()` 包装，用于说明兼容阻塞库的方法。

## 5. 预期现象

假设三个模拟操作各等待一秒：

- 串行运行约三秒；
- Task 并发运行约一秒；
- `gather` 并发运行约一秒。

这说明并发可以重叠 I/O 等待时间，但不代表 Python 把三个协程分别放到了三个线程中。协程通常仍由同一个事件循环调度。

## 6. 测试

HTTP 测试增加：

- 默认分页；
- 状态与优先级筛选；
- 第二页及超出范围页；
- 非法页码和非法枚举返回 `422`。

异步测试增加：

- 串行与并发结果一致；
- `create_task` 和 `gather` 都能完成全部工作；
- 并发耗时明显小于串行耗时；
- 阻塞函数通过 `to_thread` 执行时不会阻塞事件循环。

测试使用很短的延迟，避免拖慢验证。

## 7. 学习文档

新增 `docs/guides/async-io.md`，讲解：

- 协程、事件循环、Task、`await` 与 `gather`；
- 串行和并发的数据流；
- 为什么异步适合 I/O 密集任务；
- 为什么异步不等于多线程；
- 为什么不能在协程中直接使用 `time.sleep()`；
- 如何运行练习脚本。

同时补充现有 HTTP 指南中的工单列表和分页练习。

## 8. 明确不做

- 不实现认证接口和 JWT；
- 不接入数据库；
- 不把模拟等待加入正式 HTTP 路由；
- 不实现并发领取工单；
- 不修改 Vue；
- 不创建 Git 提交。
