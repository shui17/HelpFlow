import asyncio
import time
from collections.abc import Awaitable, Callable, Sequence


async def simulate_io(
    name: str,
    delay: float = 1.0,
    *,
    verbose: bool = True,
) -> str:
    """模拟一次不会阻塞事件循环的网络或数据库等待。"""

    if verbose:
        print(f"开始 {name}，等待 {delay:.1f} 秒")
    await asyncio.sleep(delay)
    if verbose:
        print(f"完成 {name}")
    return f"{name} 完成"


async def run_serial(
    delays: Sequence[float] = (1.0, 1.0, 1.0),
    *,
    verbose: bool = True,
) -> list[str]:
    """依次等待：前一个完成后，才开始下一个。"""

    results: list[str] = []
    for index, delay in enumerate(delays, start=1):
        result = await simulate_io(
            f"操作 {index}",
            delay,
            verbose=verbose,
        )
        results.append(result)
    return results


async def run_with_tasks(
    delays: Sequence[float] = (1.0, 1.0, 1.0),
    *,
    verbose: bool = True,
) -> list[str]:
    """先创建全部 Task,再等待它们完成。"""

    tasks = [
        asyncio.create_task(
            simulate_io(
                f"操作 {index}",
                delay,
                verbose=verbose,
            )
        )
        for index, delay in enumerate(delays, start=1)
    ]
    return [await task for task in tasks]


async def run_with_gather(
    delays: Sequence[float] = (1.0, 1.0, 1.0),
    *,
    verbose: bool = True,
) -> list[str]:
    """使用 gather 并发等待一组协程，并按传入顺序收集结果。"""

    coroutines = [
        simulate_io(
            f"操作 {index}",
            delay,
            verbose=verbose,
        )
        for index, delay in enumerate(delays, start=1)
    ]
    return list(await asyncio.gather(*coroutines))


def blocking_operation(
    name: str,
    delay: float = 1.0,
    *,
    verbose: bool = True,
) -> str:
    """模拟无法修改的同步阻塞库；不要在协程中直接调用它。"""

    if verbose:
        print(f"线程中开始 {name}，阻塞 {delay:.1f} 秒")
    time.sleep(delay)
    if verbose:
        print(f"线程中完成 {name}")
    return f"{name} 完成"


async def run_blocking_safely(
    name: str = "旧版同步库",
    delay: float = 1.0,
    *,
    verbose: bool = True,
) -> str:
    """把无法避免的阻塞函数交给线程，避免堵住事件循环。"""

    return await asyncio.to_thread(
        blocking_operation,
        name,
        delay,
        verbose=verbose,
    )


async def measure(
    label: str,
    operation: Callable[[], Awaitable[list[str]]],
) -> float:
    """运行异步操作并打印耗时。"""

    started_at = time.perf_counter()
    results = await operation()
    elapsed = time.perf_counter() - started_at
    print(f"{label}结果：{results}")
    print(f"{label}耗时：{elapsed:.2f} 秒\n")
    return elapsed


async def main() -> None:
    """依次展示串行、Task、gather 和安全包装阻塞函数。"""

    delays = (1.0, 1.0, 1.0)
    serial_elapsed = await measure(
        "串行",
        lambda: run_serial(delays),
    )
    tasks_elapsed = await measure(
        "create_task 并发",
        lambda: run_with_tasks(delays),
    )
    gather_elapsed = await measure(
        "gather 并发",
        lambda: run_with_gather(delays),
    )

    blocking_result = await run_blocking_safely()
    print(f"阻塞函数包装结果：{blocking_result}\n")
    print(
        "耗时对比："
        f"串行 {serial_elapsed:.2f}s，"
        f"Task {tasks_elapsed:.2f}s，"
        f"gather {gather_elapsed:.2f}s"
    )


if __name__ == "__main__":
    asyncio.run(main())
