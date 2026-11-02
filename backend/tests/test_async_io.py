import asyncio
import time

from examples.async_io import (
    run_blocking_safely,
    run_serial,
    run_with_gather,
    run_with_tasks,
)


def test_serial_tasks_and_gather() -> None:
    async def run_comparison() -> tuple[
        list[str],
        list[str],
        list[str],
        float,
        float,
        float,
    ]:
        delays = (0.03, 0.03, 0.03)

        started_at = time.perf_counter()
        serial_results = await run_serial(delays, verbose=False)
        serial_elapsed = time.perf_counter() - started_at

        started_at = time.perf_counter()
        task_results = await run_with_tasks(delays, verbose=False)
        task_elapsed = time.perf_counter() - started_at

        started_at = time.perf_counter()
        gather_results = await run_with_gather(delays, verbose=False)
        gather_elapsed = time.perf_counter() - started_at

        return (
            serial_results,
            task_results,
            gather_results,
            serial_elapsed,
            task_elapsed,
            gather_elapsed,
        )

    (
        serial_results,
        task_results,
        gather_results,
        serial_elapsed,
        task_elapsed,
        gather_elapsed,
    ) = asyncio.run(run_comparison())

    assert serial_results == task_results == gather_results
    assert task_elapsed < serial_elapsed * 0.7
    assert gather_elapsed < serial_elapsed * 0.7


def test_to_thread_keeps_event_loop_responsive() -> None:
    async def run_scenario() -> tuple[str, float]:
        started_at = time.perf_counter()
        blocking_task = asyncio.create_task(
            run_blocking_safely(
                "阻塞操作",
                0.2,
                verbose=False,
            )
        )

        await asyncio.sleep(0.01)
        event_loop_response_time = time.perf_counter() - started_at
        result = await blocking_task
        return result, event_loop_response_time

    result, event_loop_response_time = asyncio.run(run_scenario())

    assert result == "阻塞操作 完成"
    assert event_loop_response_time < 0.15
