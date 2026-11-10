"""Simulación de colas: cómo se comporta el servicio en las dos pruebas.

La consigna pide observar la diferencia entre el modelo cerrado (k6) y el
abierto (Vegeta). Este simulador de eventos discretos reproduce las dos
pruebas sobre distintas arquitecturas, usando los tiempos de extracción
medidos con nuestro extractor:

- **Sin backpressure (procesador compartido):** todos los pedidos que llegan
  se procesan a la vez y se reparten los núcleos. Es lo que pasa con un
  servidor que acepta todo (un hilo o tarea por pedido). Si un cliente se
  cansa de esperar, el servidor no se entera y sigue trabajando para nadie.
- **Cola central (nuestra arquitectura):** HAProxy le pasa a cada réplica
  como mucho ``slots_per_server`` pedidos; el resto espera en su cola. Un
  pedido que espera más que ``queue_timeout_s`` se descarta con 503 sin
  procesarse. El orden de salida puede ser FIFO o "PDFs chicos primero".

Es un modelo: ignora la red, el overhead HTTP y los detalles del límite de
CPU de Docker. Sirve para entender el fenómeno y comparar alternativas antes
de medir; los números finales salen de las pruebas reales con k6 y Vegeta.

Uso:
    python scripts/simulate_queues.py
    python scripts/simulate_queues.py --service-ms 5,35,464,199 --sizes-kb 91,144,720,9828
"""

from __future__ import annotations

import argparse
import heapq
import json
import math
import statistics
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

CLIENT_TIMEOUT_S = 30.0  # timeout de Vegeta en la consigna
K6_TIMEOUT_S = 60.0  # timeout por defecto de http.post en k6

OK, OVERLOADED, CLIENT_TIMEOUT = 200, 503, 0


@dataclass(frozen=True, slots=True)
class Request:
    """Lo que manda el cliente: un PDF que cuesta ``work`` segundos de CPU."""

    work: float
    size_bytes: int  # Content-Length: lo único que HAProxy sabe del PDF


@dataclass(slots=True)
class Job:
    seq: int
    arrival: float
    request: Request
    client_deadline: float
    remaining: float = field(init=False)
    started: bool = False
    server: int = -1
    abandoned: bool = False  # el cliente ya cortó; el resultado no le llega a nadie

    def __post_init__(self) -> None:
        self.remaining = self.request.work


@dataclass(frozen=True, slots=True)
class Outcome:
    seq: int
    arrival: float
    end: float
    code: int

    @property
    def latency(self) -> float:
        return self.end - self.arrival


# ---------------------------------------------------------------------------
# Políticas de servicio: deciden qué pedidos se procesan y a qué velocidad.
# assign_rates() además marca como iniciados a los que reciben CPU.
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ProcessorSharing:
    """Sin control de admisión: todos los pedidos se reparten los núcleos."""

    cores: int
    queue_timeout_s: float = math.inf

    def assign_rates(self, jobs: list[Job]) -> list[float]:
        for job in jobs:
            job.started = True  # todos entran a procesarse apenas llegan
        rate = min(1.0, self.cores / len(jobs)) if jobs else 0.0
        return [rate] * len(jobs)

    def admits(self, jobs: list[Job]) -> bool:
        return True


@dataclass(frozen=True, slots=True)
class CentralQueue:
    """Cola central de HAProxy delante de ``servers`` réplicas de 1 CPU.

    - ``slots_per_server``: pedidos simultáneos por réplica. Con más de uno,
      comparten la CPU de la réplica (equivale a EXTRACTION_WORKERS > 1).
    - ``small_first_bytes`` y ``small_boost_s``: si el primero es mayor que 0,
      los PDFs más chicos que ese tamaño se adelantan ``small_boost_s``
      segundos en la cola (infinito = pasan siempre primero).
    - ``queue_timeout_s`` y ``max_queue``: backpressure.
    """

    servers: int
    slots_per_server: int = 1
    queue_timeout_s: float = 20.0
    max_queue: float = math.inf
    small_first_bytes: int = 0
    small_boost_s: float = math.inf

    def _priority(self, job: Job) -> float:
        # Los PDFs chicos se ordenan como si hubieran llegado small_boost_s
        # segundos antes (set-priority-offset). Con infinito, pasan siempre
        # primero (set-priority-class). sorted() es estable: entre empates se
        # respeta el orden de llegada.
        if job.request.size_bytes < self.small_first_bytes:
            return job.arrival - self.small_boost_s
        return job.arrival

    def assign_rates(self, jobs: list[Job]) -> list[float]:
        load = Counter(job.server for job in jobs if job.started)
        for job in sorted((job for job in jobs if not job.started), key=self._priority):
            server = min(range(self.servers), key=lambda candidate: load[candidate])  # leastconn
            if load[server] >= self.slots_per_server:
                break  # no hay lugar libre en ninguna réplica
            job.started, job.server = True, server
            load[server] += 1
        return [1 / load[job.server] if job.started else 0.0 for job in jobs]

    def admits(self, jobs: list[Job]) -> bool:
        # Un lugar libre nunca queda ocioso: esperan los que exceden la
        # capacidad, aunque varios hayan llegado en el mismo instante.
        waiting = len(jobs) - self.servers * self.slots_per_server
        return waiting < self.max_queue


# ---------------------------------------------------------------------------
# Motor de simulación
# ---------------------------------------------------------------------------


class Simulation:
    """Avanza de evento en evento: llegadas, fines de proceso y vencimientos.

    ``on_outcome`` se llama cada vez que un pedido recibe respuesta (o el
    cliente corta) y puede programar nuevas llegadas: así se modela k6, donde
    cada usuario virtual manda el próximo pedido cuando recibe la respuesta.
    """

    def __init__(self, policy: ProcessorSharing | CentralQueue, client_timeout: float) -> None:
        self.policy = policy
        self.client_timeout = client_timeout
        self.now = 0.0
        self.jobs: list[Job] = []
        self.outcomes: list[Outcome] = []
        self._arrivals: list[tuple[float, int, Request]] = []
        self._next_seq = 0
        self.on_outcome: Callable[[Outcome], None] = lambda outcome: None

    def schedule_arrival(self, time: float, request: Request) -> int:
        seq = self._next_seq
        self._next_seq += 1
        heapq.heappush(self._arrivals, (time, seq, request))
        return seq

    def run(self) -> list[Outcome]:
        while self._arrivals or self.jobs:
            rates = self.policy.assign_rates(self.jobs)
            next_event = self._arrivals[0][0] if self._arrivals else math.inf
            for job, rate in zip(self.jobs, rates, strict=True):
                if rate > 0:
                    next_event = min(next_event, self.now + job.remaining / rate)
                if not job.abandoned:
                    next_event = min(next_event, job.client_deadline)
                if not job.started:
                    next_event = min(next_event, job.arrival + self.policy.queue_timeout_s)

            elapsed = next_event - self.now
            for job, rate in zip(self.jobs, rates, strict=True):
                job.remaining -= rate * elapsed
            self.now = next_event
            self._handle_due_events()
        return self.outcomes

    def _record(self, job: Job, code: int) -> None:
        outcome = Outcome(job.seq, job.arrival, self.now, code)
        self.outcomes.append(outcome)
        self.on_outcome(outcome)

    def _handle_due_events(self) -> None:
        epsilon = 1e-9
        still_active = []
        for job in self.jobs:
            if job.started and job.remaining <= epsilon:
                if not job.abandoned:
                    self._record(job, OK)
            elif not job.started and self.now >= job.arrival + self.policy.queue_timeout_s - epsilon:
                self._record(job, OVERLOADED)  # descartado sin procesar
            elif not job.abandoned and self.now >= job.client_deadline - epsilon:
                job.abandoned = True
                self._record(job, CLIENT_TIMEOUT)
                if job.started:
                    still_active.append(job)  # el servidor sigue trabajando "para nadie"
                # Si estaba en cola, HAProxy lo saca (abortonclose).
            else:
                still_active.append(job)
        self.jobs = still_active

        while self._arrivals and self._arrivals[0][0] <= self.now + epsilon:
            time, seq, request = heapq.heappop(self._arrivals)
            job = Job(seq, time, request, client_deadline=time + self.client_timeout)
            if self.policy.admits(self.jobs):
                self.jobs.append(job)
            else:
                self._record(job, OVERLOADED)


# ---------------------------------------------------------------------------
# Las dos pruebas de la consigna
# ---------------------------------------------------------------------------


def vegeta_test(policy, pdfs: list[Request], rate: float = 50, duration: float = 30) -> dict:
    """Modelo abierto: ``rate`` pedidos por segundo pase lo que pase."""
    simulation = Simulation(policy, CLIENT_TIMEOUT_S)
    total = round(rate * duration)
    for i in range(total):
        simulation.schedule_arrival(i / rate, pdfs[i % len(pdfs)])
    outcomes = simulation.run()

    successes = [o for o in outcomes if o.code == OK]
    end = max(o.end for o in outcomes)
    return {
        "requests": total,
        "successes": len(successes),
        "success_rate": len(successes) / total,
        "client_timeouts": sum(o.code == CLIENT_TIMEOUT for o in outcomes),
        "rejected_503": sum(o.code == OVERLOADED for o in outcomes),
        # Throughput de Vegeta: éxitos / (duración del ataque + espera hasta
        # la última respuesta), es decir, desde el primer pedido hasta el final.
        "throughput": len(successes) / end,
        "p50_all_s": statistics.median(o.latency for o in outcomes),
        "p50_success_s": statistics.median(o.latency for o in successes) if successes else math.nan,
    }


def k6_spike_test(policy, pdfs: list[Request], vus: int = 100) -> dict:
    """Modelo cerrado: rampa 0→100 VUs en 10 s, 20 s a 100, rampa 100→0 en 10 s.

    Cada VU manda un pedido, espera la respuesta y manda el siguiente. En la
    rampa de bajada, k6 deja de iniciar iteraciones nuevas en los VUs que va
    apagando, pero deja terminar la que está en curso.
    """
    simulation = Simulation(policy, K6_TIMEOUT_S)
    start = {vu: 10 * vu / vus for vu in range(1, vus + 1)}
    stop = {vu: 30 + 10 * (vus - vu) / vus for vu in range(1, vus + 1)}
    owner: dict[int, tuple[int, int]] = {}  # seq → (vu, iteración)

    def send(vu: int, iteration: int, time: float) -> None:
        if time < stop[vu]:
            pdf = pdfs[(vu + iteration) % len(pdfs)]  # misma rotación que spike.js
            owner[simulation.schedule_arrival(time, pdf)] = (vu, iteration)

    def on_outcome(outcome: Outcome) -> None:
        vu, iteration = owner[outcome.seq]
        send(vu, iteration + 1, outcome.end)

    simulation.on_outcome = on_outcome
    for vu in start:
        send(vu, 0, start[vu])
    outcomes = simulation.run()

    latencies = sorted(o.latency for o in outcomes)
    duration = max(40.0, max(o.end for o in outcomes))
    return {
        "requests": len(outcomes),
        "rate": len(outcomes) / duration,
        "error_rate": sum(o.code != OK for o in outcomes) / len(outcomes),
        "p50_s": percentile(latencies, 50),
        "p90_s": percentile(latencies, 90),
        "p95_s": percentile(latencies, 95),
        "max_s": latencies[-1],
    }


def percentile(ordered: list[float], p: float) -> float:
    """Percentil con interpolación lineal entre los dos valores más cercanos."""
    position = (len(ordered) - 1) * p / 100
    low, high = math.floor(position), math.ceil(position)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def scenarios(servers: int) -> dict[str, ProcessorSharing | CentralQueue]:
    small = 256 * 1024
    return {
        "Sin backpressure (procesador compartido)": ProcessorSharing(servers),
        "Cola FIFO, espera máx. 20 s": CentralQueue(servers, queue_timeout_s=20),
        "Cola FIFO, espera máx. 25 s (elegida)": CentralQueue(servers, queue_timeout_s=25),
        "Cola FIFO 25 s, 2 extracciones por réplica": CentralQueue(servers, slots_per_server=2, queue_timeout_s=25),
        "Chicos primero (+2 s), espera máx. 25 s": CentralQueue(
            servers, queue_timeout_s=25, small_first_bytes=small, small_boost_s=2
        ),
        "Chicos siempre primero, espera máx. 25 s": CentralQueue(servers, queue_timeout_s=25, small_first_bytes=small),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--service-ms",
        default="5,35,464,199",
        help="Tiempo de extracción de cada PDF en ms (por defecto: docs/investigacion/benchmark_extraccion.json)",
    )
    parser.add_argument(
        "--sizes-kb",
        default="91,144,720,9828",
        help="Tamaño de cada PDF de prueba en KB (por defecto, los de tests/stress/pdfs)",
    )
    parser.add_argument("--servers", type=int, default=5, help="Réplicas (1 CPU cada una)")
    parser.add_argument("--output", type=Path, default=Path("docs/investigacion/simulacion_colas.json"))
    args = parser.parse_args()

    works = [float(ms) / 1000 for ms in args.service_ms.split(",")]
    sizes = [int(float(kb) * 1024) for kb in args.sizes_kb.split(",")]
    pdfs = [Request(work, size) for work, size in zip(works, sizes, strict=True)]
    mean_work = statistics.mean(works)
    capacity = args.servers / mean_work
    print(
        f"Capacidad teórica: {capacity:.1f} req/s ({args.servers} réplicas, servicio medio {mean_work * 1000:.0f} ms)"
    )
    print()

    results: dict = {"capacity_rps": capacity, "service_times_s": works, "sizes_bytes": sizes, "k6": {}, "vegeta": {}}
    print(f"{'k6 spike':<42}{'pedidos':>9}{'req/s':>8}{'error':>8}{'p50':>8}{'p90':>8}{'p95':>8}{'máx':>8}")
    for name, policy in scenarios(args.servers).items():
        r = results["k6"][name] = k6_spike_test(policy, pdfs)
        print(
            f"{name:<42}{r['requests']:>9}{r['rate']:>8.2f}{r['error_rate']:>8.1%}{r['p50_s']:>8.2f}"
            f"{r['p90_s']:>8.2f}{r['p95_s']:>8.2f}{r['max_s']:>8.2f}"
        )

    print(f"\n{'Vegeta 50 req/s':<42}{'éxito':>8}{'timeouts':>10}{'503':>6}{'thr':>8}{'p50':>8}{'p50 ok':>8}")
    for name, policy in scenarios(args.servers).items():
        r = results["vegeta"][name] = vegeta_test(policy, pdfs)
        print(
            f"{name:<42}{r['success_rate']:>8.1%}{r['client_timeouts']:>10}{r['rejected_503']:>6}"
            f"{r['throughput']:>8.2f}{r['p50_all_s']:>8.2f}{r['p50_success_s']:>8.2f}"
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    # newline="\n": el JSON queda con fin de línea LF también en Windows.
    report = json.dumps(results, indent=2, ensure_ascii=False)
    args.output.write_text(report, encoding="utf-8", newline="\n")
    print(f"\nResultados guardados en {args.output}")


if __name__ == "__main__":
    main()
