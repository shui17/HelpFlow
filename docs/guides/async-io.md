# HelpFlow asyncio 并发指南

## 1. 运行练习

在 PowerShell 中执行：

```powershell
cd D:\vscode\HelpFlow\backend
.\.venv\Scripts\python.exe -m examples.async_io
```

脚本会依次运行：

1. 串行等待三个模拟 I/O；
2. 使用 `create_task` 并发等待；
3. 使用 `gather` 并发等待；
4. 使用 `to_thread` 安全调用一个阻塞函数。

三个操作各等待一秒时，通常会看到：

```text
串行耗时：约 3 秒
create_task 并发耗时：约 1 秒
gather 并发耗时：约 1 秒
```

具体数值会受电脑负载影响，重点是并发耗时接近最慢的单次等待，而不是三次等待之和。

## 2. 什么是协程

使用 `async def` 定义的函数叫协程函数：

```python
async def simulate_io():
    await asyncio.sleep(1)
```

调用协程函数不会像普通函数那样立刻把全部代码执行完，而是产生一个协程对象。协程需要由事件循环运行，并在遇到 `await` 时暂停，把执行机会交给其他任务。

```text
协程 A 执行
   ↓ 遇到 await，暂停
协程 B 执行
   ↓ 遇到 await，暂停
事件循环等待 I/O 就绪
   ↓
恢复可以继续运行的协程
```

## 3. 事件循环

事件循环可以理解为异步程序的调度中心。它反复执行三件事：

1. 找出现在可以运行的任务；
2. 运行任务，直到任务结束或遇到 `await`；
3. 等待定时器、网络或数据库等 I/O 事件完成。

脚本入口使用：

```python
asyncio.run(main())
```

`asyncio.run` 会创建事件循环、运行 `main`，最后关闭事件循环。普通脚本通常只在最外层调用一次。

## 4. 为什么连续 await 是串行的

下面的写法会先等第一个完成，再创建和等待第二个：

```python
first = await simulate_io("操作 1")
second = await simulate_io("操作 2")
```

虽然使用了 `async` 和 `await`，但这仍然是串行流程。`async` 不会自动让代码并发。

本项目的 `run_serial()` 正是为了展示这一点。

## 5. create_task

`asyncio.create_task()` 把一个协程包装成 Task，并安排它在事件循环中运行：

```python
first_task = asyncio.create_task(simulate_io("操作 1"))
second_task = asyncio.create_task(simulate_io("操作 2"))

first = await first_task
second = await second_task
```

两个 Task 在第一次 `await` 前都已经创建，因此它们的等待时间可以重叠。

Task 适合以下情况：

- 需要保存任务对象；
- 稍后再等待结果；
- 需要取消任务；
- 需要分别检查任务状态。

创建 Task 后必须妥善等待或管理它，不能随意丢弃。

## 6. gather

`asyncio.gather()` 适合“同时运行一组协程，最后收集全部结果”：

```python
results = await asyncio.gather(
    simulate_io("操作 1"),
    simulate_io("操作 2"),
    simulate_io("操作 3"),
)
```

结果顺序与传入协程的顺序一致，不取决于谁先完成。

在 HelpFlow 后续真实项目中，如果一个接口需要同时读取彼此独立的多个外部数据源，`gather` 可能有用。但对同一个数据库 Session 并发执行操作通常需要额外考虑连接和事务安全，不能机械套用。

## 7. 异步为什么适合 I/O 密集任务

I/O 密集任务的大部分时间花在等待，例如：

- 等待 MySQL 返回查询结果；
- 等待另一个 HTTP 服务响应；
- 等待文件读取；
- 等待定时器。

等待期间 CPU 没有必要一直停在当前任务上。协程可以在 `await` 处让出执行机会，让事件循环处理其他请求。

如果三个请求各自等待数据库一秒，并发并不是让数据库查询本身变快，而是让三个等待时间尽量重叠。

## 8. 异步不等于多线程

普通 `asyncio` 协程通常运行在同一个线程中，由事件循环合作式调度：

```text
一个线程
  └─ 一个事件循环
       ├─ Task A
       ├─ Task B
       └─ Task C
```

只有当协程主动遇到 `await` 时，其他任务才有机会运行。因此：

- 异步并不自动创建多个线程；
- 异步主要提高等待型任务的吞吐量；
- CPU 密集计算不会因为加上 `async` 就自动变快。

## 9. 为什么不能在协程中直接 time.sleep

错误示例：

```python
async def wrong():
    time.sleep(1)
```

`time.sleep` 不认识事件循环，它会直接阻塞当前线程。如果事件循环就在这个线程中，那么其他所有协程也无法运行。

异步代码中的定时等待应该使用：

```python
await asyncio.sleep(1)
```

如果必须调用无法修改的同步阻塞库，可以使用：

```python
result = await asyncio.to_thread(blocking_operation)
```

`to_thread` 会把阻塞函数放到线程中运行，因此事件循环可以继续处理其他协程。但它是兼容同步库的手段，不代表所有函数都应该放进线程。

## 10. 对照项目代码阅读

建议按以下顺序阅读 `backend/examples/async_io.py`：

1. `simulate_io()`：观察 `async def` 和 `await`；
2. `run_serial()`：理解连续等待为何仍然串行；
3. `run_with_tasks()`：理解 Task 创建时机；
4. `run_with_gather()`：理解批量并发和结果收集；
5. `blocking_operation()`：识别阻塞函数；
6. `run_blocking_safely()`：理解 `to_thread`；
7. `main()`：观察事件循环入口和耗时对比。

## 11. 本阶段应达到的程度

进入下一阶段前，你应该能回答：

- 协程和普通函数有什么区别？
- `await` 时程序发生了什么？
- 为什么连续三个 `await` 可能仍然是串行？
- `create_task` 和 `gather` 各适合什么场景？
- 为什么 `time.sleep` 会阻塞 FastAPI 的异步处理？
- 异步为什么适合数据库和网络 I/O？
- 异步为什么不等于多线程？

你不需要自己实现事件循环，也不需要记住 `asyncio` 的全部 API。能够运行示例、预测耗时并解释上述问题，就达到了阶段 2 的目标。
