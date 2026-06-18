"""Tests for pya3eda.runner.throttle.Throttler."""

from __future__ import annotations

import pytest

from pya3eda.runner.throttle import Throttler, ThrottleTimeoutError


class TestConstruction:
    def test_rejects_zero_cores(self) -> None:
        with pytest.raises(ValueError, match="max_cores must be"):
            Throttler(max_cores=0)


class TestRegisterAndState:
    def test_register_charges_cores(self) -> None:
        t = Throttler(max_cores=8)
        t.register("j1", 4)
        assert t.cores_in_use == 4
        assert t.active_jobs == ("j1",)

    def test_register_rejects_zero(self) -> None:
        t = Throttler(max_cores=8)
        with pytest.raises(ValueError, match="cores must be"):
            t.register("j1", 0)


class TestWaitForRoom:
    def test_returns_immediately_when_room(self) -> None:
        t = Throttler(max_cores=8)
        t.wait_for_room(4, is_finished=lambda _j: True)  # no active jobs → room
        assert t.cores_in_use == 0

    def test_rejects_request_over_budget(self) -> None:
        t = Throttler(max_cores=4)
        with pytest.raises(ValueError, match="exceeds the total budget"):
            t.wait_for_room(8, is_finished=lambda _j: True)

    def test_reaps_then_admits(self, monkeypatch: pytest.MonkeyPatch) -> None:
        t = Throttler(max_cores=4, poll_interval=0)
        t.register("j1", 4)  # full
        # j1 finishes on first reap → room frees up, no sleep needed
        t.wait_for_room(4, is_finished=lambda _j: True)
        assert t.active_jobs == ()

    def test_sleeps_until_room(self, monkeypatch: pytest.MonkeyPatch) -> None:
        t = Throttler(max_cores=4, poll_interval=0.01)
        t.register("j1", 4)
        calls = {"n": 0}

        def is_finished(_j: str) -> bool:
            calls["n"] += 1
            return calls["n"] >= 2  # not finished on the first poll, finished on the second

        sleeps: list[float] = []
        monkeypatch.setattr("pya3eda.runner.throttle.time.sleep", lambda s: sleeps.append(s))
        t.wait_for_room(4, is_finished=is_finished)
        assert sleeps == [0.01]  # slept exactly once before room freed

    def test_timeout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        t = Throttler(max_cores=4, poll_interval=0)
        t.register("j1", 4)
        monkeypatch.setattr("pya3eda.runner.throttle.time.sleep", lambda _s: None)
        with pytest.raises(ThrottleTimeoutError, match="timed out"):
            t.wait_for_room(4, is_finished=lambda _j: False, max_wait_seconds=0)


class TestWaitAll:
    def test_returns_when_empty(self) -> None:
        Throttler(max_cores=4).wait_all(is_finished=lambda _j: True)  # no jobs

    def test_blocks_until_all_done(self) -> None:
        t = Throttler(max_cores=8)
        t.register("j1", 4)
        t.register("j2", 4)
        t.wait_all(is_finished=lambda _j: True)
        assert t.active_jobs == ()

    def test_sleeps_until_done(self, monkeypatch: pytest.MonkeyPatch) -> None:
        t = Throttler(max_cores=4, poll_interval=0.01)
        t.register("j1", 4)
        calls = {"n": 0}

        def is_finished(_j: str) -> bool:
            calls["n"] += 1
            return calls["n"] >= 2  # still running on the first poll

        sleeps: list[float] = []
        monkeypatch.setattr("pya3eda.runner.throttle.time.sleep", lambda s: sleeps.append(s))
        t.wait_all(is_finished=is_finished)
        assert sleeps == [0.01]

    def test_timeout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        t = Throttler(max_cores=4, poll_interval=0)
        t.register("j1", 4)
        monkeypatch.setattr("pya3eda.runner.throttle.time.sleep", lambda _s: None)
        with pytest.raises(ThrottleTimeoutError, match="all jobs"):
            t.wait_all(is_finished=lambda _j: False, max_wait_seconds=0)
