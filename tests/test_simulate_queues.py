"""Tests del simulador de colas con casos que se pueden calcular a mano."""

import math

import pytest
from simulate_queues import (
    CLIENT_TIMEOUT,
    OK,
    OVERLOADED,
    CentralQueue,
    ProcessorSharing,
    Request,
    Simulation,
    percentile,
    vegeta_test,
)

SMALL = Request(work=0.1, size_bytes=10_000)
BIG = Request(work=1.0, size_bytes=5_000_000)


def run(policy, arrivals, client_timeout=30.0):
    simulation = Simulation(policy, client_timeout)
    for time, request in arrivals:
        simulation.schedule_arrival(time, request)
    return sorted(simulation.run(), key=lambda outcome: outcome.seq)


def test_single_request_takes_exactly_its_service_time():
    (outcome,) = run(CentralQueue(servers=1), [(0.0, BIG)])

    assert (outcome.code, outcome.latency) == (OK, pytest.approx(1.0))


def test_fifo_serves_in_arrival_order_and_the_second_one_waits():
    first, second = run(CentralQueue(servers=1), [(0.0, BIG), (0.0, BIG)])

    assert (first.end, second.end) == (pytest.approx(1.0), pytest.approx(2.0))


def test_processor_sharing_splits_the_cpu_and_both_finish_late():
    first, second = run(ProcessorSharing(cores=1), [(0.0, BIG), (0.0, BIG)])

    assert (first.end, second.end) == (pytest.approx(2.0), pytest.approx(2.0))


def test_two_slots_per_server_share_its_cpu():
    first, second = run(CentralQueue(servers=1, slots_per_server=2), [(0.0, BIG), (0.0, BIG)])

    assert (first.end, second.end) == (pytest.approx(2.0), pytest.approx(2.0))


def test_small_first_lets_a_small_pdf_skip_the_queue():
    # Ocupado con un PDF grande; llegan otro grande y uno chico.
    arrivals = [(0.0, BIG), (0.1, BIG), (0.2, SMALL)]

    _, waiting_big, small = run(CentralQueue(servers=1, small_first_bytes=100_000), arrivals)

    assert small.end == pytest.approx(1.1)  # sale apenas se libera la réplica
    assert waiting_big.end == pytest.approx(2.1)


def test_request_waiting_longer_than_queue_timeout_gets_503_without_processing():
    _, discarded = run(CentralQueue(servers=1, queue_timeout_s=0.5), [(0.0, BIG), (0.0, BIG)])

    assert (discarded.code, discarded.end) == (OVERLOADED, pytest.approx(0.5))


def test_full_queue_rejects_on_arrival():
    _, _, rejected = run(CentralQueue(servers=1, max_queue=1), [(0.0, BIG), (0.0, BIG), (0.0, BIG)])

    assert (rejected.code, rejected.latency) == (OVERLOADED, 0.0)


def test_client_gives_up_at_its_timeout():
    (outcome,) = run(ProcessorSharing(cores=1), [(0.0, Request(work=5.0, size_bytes=1))], client_timeout=2.0)

    assert (outcome.code, outcome.end) == (CLIENT_TIMEOUT, pytest.approx(2.0))


def test_below_capacity_every_vegeta_request_succeeds():
    result = vegeta_test(CentralQueue(servers=2), [SMALL], rate=5, duration=4)

    assert result["success_rate"] == 1.0
    assert result["p50_all_s"] == pytest.approx(0.1)


def test_overload_hurts_processor_sharing_more_than_a_queue_with_backpressure():
    pdfs = [SMALL, Request(work=0.4, size_bytes=1_000_000)]  # 2 servidores: 8 req/s; llegan 16
    shared = vegeta_test(ProcessorSharing(cores=2), pdfs, rate=16, duration=30)
    queued = vegeta_test(CentralQueue(servers=2, queue_timeout_s=20), pdfs, rate=16, duration=30)

    assert queued["successes"] > shared["successes"]


def test_percentile_interpolates_between_values():
    assert percentile([1.0, 2.0, 3.0, 4.0], 50) == 2.5
    assert percentile([1.0, 2.0, 3.0, 4.0], 100) == 4.0
    assert math.isclose(percentile([0.0, 10.0], 90), 9.0)
