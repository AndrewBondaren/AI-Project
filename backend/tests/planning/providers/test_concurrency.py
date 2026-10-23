"""Deterministic single-flight, queue, cancellation and shutdown scenarios."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
import unittest

from app.application.planning.service.planningService import (
    PlanBuildFailure, PlanContractFailure, PlanWaitCancelled, PlanWaitTimeout, PlanningBusy,
)
from app.dataModel.planning.contracts.planEnvelope import PlanBuildResult
from app.dataModel.planning.policy.planningExecutionPolicy import PlanningExecutionPolicy
from tests.planning.providers.test_domain_providers import Data, Harness, Provider, Wait, contract


class TrackingWait(Wait):
    def __init__(self, seconds=5):
        super().__init__(seconds)
        self.entered = Event()
        self.calls = 0

    def raise_if_cancelled(self):
        super().raise_if_cancelled()
        self.calls += 1
        if self.calls >= 3:
            self.entered.set()


class ConcurrencyTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness(policy=PlanningExecutionPolicy(max_workers=1, max_pending_builds=1))
        self.started, self.release = Event(), Event()
        self.addCleanup(self.h.service.shutdown)
        self.addCleanup(self.release.set)

    def blocked(self, request, dependencies, control):
        self.started.set()
        if not self.release.wait(5):
            raise AssertionError("test did not release provider")
        control.raise_if_shutdown()
        return PlanBuildResult[Data](payload=Data(value=request.inputs.value), diagnostics=())

    def test_same_key_concurrent_misses_build_once(self):
        binding, provider = self.h.register(provider=Provider(self.blocked))
        waits = [TrackingWait() for _ in range(8)]
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(self.h.get, binding, wait=wait) for wait in waits]
            try:
                for wait in waits:
                    self.assertTrue(wait.entered.wait(2))
                self.assertEqual(provider.count, 1)
            finally:
                self.release.set()
            outputs = [future.result(2) for future in futures]
        self.assertTrue(all(result == outputs[0] for result in outputs))
        self.assertEqual(provider.count, 1)
        self.assertEqual(len(self.h.service._flights), 0)

    def test_cancelling_initiator_does_not_cancel_shared_worker(self):
        binding, provider = self.h.register(provider=Provider(self.blocked))
        first, second = TrackingWait(), TrackingWait()
        with ThreadPoolExecutor(max_workers=2) as pool:
            initiator = pool.submit(self.h.get, binding, wait=first)
            self.assertTrue(first.entered.wait(2))
            survivor = pool.submit(self.h.get, binding, wait=second)
            try:
                self.assertTrue(second.entered.wait(2))
                first.cancelled.set()
                with self.assertRaises(PlanWaitCancelled):
                    initiator.result(2)
            finally:
                self.release.set()
            self.assertEqual(survivor.result(2).payload.value, 2)
        self.assertEqual(provider.count, 1)
        self.assertEqual(self.h.get(binding).payload.value, 2)

    def test_deadline_only_detaches_that_waiter(self):
        binding, provider = self.h.register(provider=Provider(self.blocked))
        expired, survivor_wait = TrackingWait(0.15), TrackingWait()
        with ThreadPoolExecutor(max_workers=2) as pool:
            timed = pool.submit(self.h.get, binding, wait=expired)
            self.assertTrue(expired.entered.wait(2))
            survivor = pool.submit(self.h.get, binding, wait=survivor_wait)
            try:
                self.assertTrue(survivor_wait.entered.wait(2))
                with self.assertRaises(PlanWaitTimeout):
                    timed.result(2)
            finally:
                self.release.set()
            self.assertEqual(survivor.result(2).payload.value, 2)
        self.assertEqual(provider.count, 1)

    def test_all_waiters_cancelled_worker_remains_joinable_then_releases_flight(self):
        binding, provider = self.h.register(provider=Provider(self.blocked))
        wait = TrackingWait()
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(self.h.get, binding, wait=wait)
            try:
                self.assertTrue(wait.entered.wait(2))
                wait.cancelled.set()
                with self.assertRaises(PlanWaitCancelled):
                    pending.result(2)
                self.assertEqual(len(self.h.service._flights), 1)
            finally:
                self.release.set()
        self.assertEqual(self.h.get(binding).payload.value, 2)
        self.assertEqual(provider.count, 1)
        self.assertEqual(len(self.h.service._flights), 0)

    def test_shared_failure_delivered_to_all_then_retry(self):
        def fail(*args):
            self.blocked(*args)
            raise ValueError("failure shared by all waiters")
        binding, provider = self.h.register(provider=Provider(fail))
        waits = [TrackingWait() for _ in range(4)]
        failures = []
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(self.h.get, binding, wait=wait) for wait in waits]
            try:
                for wait in waits:
                    self.assertTrue(wait.entered.wait(2))
            finally:
                self.release.set()
            for future in futures:
                with self.assertRaises(PlanBuildFailure) as caught:
                    future.result(2)
                failures.append(caught.exception)
        self.assertTrue(all(failure is failures[0] for failure in failures))
        self.assertEqual(provider.count, 1)
        with self.assertRaises(PlanBuildFailure):
            self.h.get(binding)
        self.assertEqual(provider.count, 2)

    def test_queue_is_bounded_but_same_key_can_join_when_full(self):
        binding, provider = self.h.register(provider=Provider(self.blocked))
        waits = [TrackingWait() for _ in range(3)]
        with ThreadPoolExecutor(max_workers=3) as pool:
            first = pool.submit(self.h.get, binding, value=1, wait=waits[0])
            self.assertTrue(self.started.wait(2))
            queued = pool.submit(self.h.get, binding, value=2, wait=waits[1])
            try:
                self.assertTrue(waits[1].entered.wait(2))
                with self.assertRaises(PlanningBusy):
                    self.h.get(binding, value=3)
                joined = pool.submit(self.h.get, binding, value=1, wait=waits[2])
                self.assertTrue(waits[2].entered.wait(2))
            finally:
                self.release.set()
            self.assertEqual(first.result(2), joined.result(2))
            self.assertEqual(queued.result(2).payload.value, 2)
        self.assertEqual(provider.count, 2)

    def test_shutdown_wakes_waiters_stops_queue_and_prevents_publication(self):
        binding, _ = self.h.register(provider=Provider(self.blocked))
        waits = [TrackingWait(), TrackingWait()]
        with ThreadPoolExecutor(max_workers=2) as pool:
            active = pool.submit(self.h.get, binding, value=1, wait=waits[0])
            self.assertTrue(self.started.wait(2))
            queued = pool.submit(self.h.get, binding, value=2, wait=waits[1])
            try:
                self.assertTrue(waits[1].entered.wait(2))
                self.h.service.shutdown(wait=False)
                for future in (active, queued):
                    with self.assertRaises(PlanWaitCancelled):
                        future.result(2)
                with self.assertRaises(PlanWaitCancelled):
                    self.h.get(binding)
            finally:
                self.release.set()
        self.h.service.shutdown()
        self.assertEqual(self.h.backend.retained_bytes, 0)
        self.assertEqual(len(self.h.service._flights), 0)

    def test_recursive_provider_request_fails_without_executor_deadlock(self):
        binding = contract()
        provider = Provider(lambda *args: self.h.get(binding))
        self.h.register(binding, provider)
        with self.assertRaises(PlanContractFailure):
            self.h.get(binding)
        self.assertEqual(provider.count, 1)

    def test_old_revision_finishing_after_new_revision_never_becomes_current(self):
        parallel = Harness(policy=PlanningExecutionPolicy(max_workers=2, max_pending_builds=1))
        self.addCleanup(parallel.service.shutdown)

        def build(req, deps, ctl):
            if req.inputs.value == 1:
                return self.blocked(req, deps, ctl)
            return PlanBuildResult[Data](payload=Data(value=req.inputs.value), diagnostics=())

        binding, _ = parallel.register(provider=Provider(build))
        with ThreadPoolExecutor(max_workers=1) as pool:
            old = pool.submit(parallel.get, binding, value=1)
            try:
                self.assertTrue(self.started.wait(2))
                current = parallel.get(binding, value=2)
            finally:
                self.release.set()
            self.assertNotEqual(old.result(2).ref, current.ref)
        self.assertEqual(parallel.get(binding, value=2), current)


if __name__ == "__main__":
    unittest.main()
