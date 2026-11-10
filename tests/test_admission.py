"""Tests del control de admisión (backpressure).

Los escenarios se arman con eventos de asyncio en lugar de sleeps, para que
el orden sea determinístico y los tests no dependan de la velocidad de la PC.
"""

import asyncio

import pytest

from App.domain.exceptions import QueueFullError, QueueTimeoutError
from App.services.admission import AdmissionController


async def hold_slot(admission: AdmissionController, acquired: asyncio.Event, release: asyncio.Event) -> None:
    async with admission.slot():
        acquired.set()
        await release.wait()


def test_requests_wait_in_the_queue_until_a_slot_is_free():
    async def scenario():
        admission = AdmissionController(max_concurrent=1, max_waiting=1, wait_timeout=5)
        acquired, release = asyncio.Event(), asyncio.Event()
        holder = asyncio.create_task(hold_slot(admission, acquired, release))
        await acquired.wait()

        waiter = asyncio.create_task(hold_slot(admission, asyncio.Event(), asyncio.Event()))
        await asyncio.sleep(0)  # deja que el segundo pedido entre a la cola
        queued_while_busy = (admission.running, admission.waiting)

        release.set()
        await holder
        await asyncio.sleep(0)
        waiter.cancel()
        return queued_while_busy

    assert asyncio.run(scenario()) == (1, 1)


def test_request_is_rejected_immediately_when_the_queue_is_full():
    async def scenario():
        admission = AdmissionController(max_concurrent=1, max_waiting=0, wait_timeout=5)
        acquired, release = asyncio.Event(), asyncio.Event()
        holder = asyncio.create_task(hold_slot(admission, acquired, release))
        await acquired.wait()
        try:
            async with admission.slot():
                pass
        finally:
            release.set()
            await holder

    with pytest.raises(QueueFullError):
        asyncio.run(scenario())


def test_request_that_waits_too_long_is_discarded():
    async def scenario():
        admission = AdmissionController(max_concurrent=1, max_waiting=1, wait_timeout=0.05)
        acquired, release = asyncio.Event(), asyncio.Event()
        holder = asyncio.create_task(hold_slot(admission, acquired, release))
        await acquired.wait()
        try:
            async with admission.slot():
                pass
        finally:
            release.set()
            await holder

    with pytest.raises(QueueTimeoutError):
        asyncio.run(scenario())


def test_counters_return_to_zero_after_success_and_after_timeout():
    async def scenario():
        admission = AdmissionController(max_concurrent=1, max_waiting=1, wait_timeout=0.05)
        acquired, release = asyncio.Event(), asyncio.Event()
        holder = asyncio.create_task(hold_slot(admission, acquired, release))
        await acquired.wait()
        with pytest.raises(QueueTimeoutError):
            async with admission.slot():
                pass
        release.set()
        await holder
        return admission.running, admission.waiting

    assert asyncio.run(scenario()) == (0, 0)


def test_slot_reports_how_long_the_request_waited():
    async def scenario():
        admission = AdmissionController(max_concurrent=1, max_waiting=1, wait_timeout=5)
        async with admission.slot() as queued_seconds:
            return queued_seconds

    assert 0 <= asyncio.run(scenario()) < 0.1
