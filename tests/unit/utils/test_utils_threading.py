import threading
from typing import Any

import pytest

from opencode_status_bar.utils.threading import run_in_background, start_background_task


class TestRunInBackground:
    def test_decorator_properties(self):
        results: dict[str, Any] = {"thread_id": None, "daemon": None}
        main_thread_id = threading.current_thread().ident
        done = threading.Event()

        @run_in_background
        def my_special_function():
            results["thread_id"] = threading.current_thread().ident
            results["daemon"] = threading.current_thread().daemon
            done.set()

        assert my_special_function.__name__ == "my_special_function"

        return_value = my_special_function()
        assert return_value == None

        done.wait(timeout=1)

        assert results["thread_id"] != main_thread_id
        assert results["daemon"]

    @pytest.mark.parametrize(
        "args,kwargs,expected",
        [
            ((5, 3), {}, 8),
            ((10, 20), {}, 30),
            ((1,), {"b": 7}, 8),
            ((), {"a": 100, "b": 200}, 300),
        ],
        ids=["positional", "large-positional", "mixed", "kwargs-only"],
    )
    def test_with_arguments(self, args, kwargs, expected):
        results: list[int] = []
        done = threading.Event()

        @run_in_background
        def add_numbers(a, b):
            results.append(a + b)
            done.set()

        add_numbers(*args, **kwargs)
        done.wait(timeout=1)

        assert len(results) == 1
        assert results[0] == expected

    def test_concurrent_execution(self):
        results: list[int] = []
        barrier = threading.Barrier(4)

        @run_in_background
        def append_value(value):
            results.append(value)
            barrier.wait(timeout=1)

        append_value(1)
        append_value(2)
        append_value(3)

        barrier.wait(timeout=1)

        assert sorted(results) == [1, 2, 3]


class TestStartBackgroundTask:
    def test_thread_properties_and_lifecycle(self):
        results: dict[str, Any] = {"thread_id": None, "started": False}
        main_thread_id = threading.current_thread().ident
        started_event = threading.Event()

        def task_function():
            results["thread_id"] = threading.current_thread().ident
            results["started"] = True
            started_event.set()

        thread = start_background_task(task_function)

        assert type(thread).__name__ == "Thread"
        assert thread.daemon

        wait_result = started_event.wait(timeout=1)
        assert wait_result

        thread.join(timeout=1)

        assert results["thread_id"] != main_thread_id
        assert results["started"]
