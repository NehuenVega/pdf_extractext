"""Tests del pool de procesos.

Usan funciones de la biblioteca estándar (``math.sqrt``, ``os._exit``) como
tareas: se pueden enviar a otro proceso sin definir funciones de prueba.
"""

import asyncio
import math
import os

import pytest

from App.domain.exceptions import WorkerCrashedError
from App.infrastructure.worker_pool import WorkerPool


def test_runs_the_function_in_another_process():
    async def scenario():
        pool = WorkerPool(size=1)
        try:
            return await pool.run(os.getpid)
        finally:
            pool.close()

    assert asyncio.run(scenario()) != os.getpid()


def test_pool_recovers_after_a_worker_dies():
    async def scenario():
        pool = WorkerPool(size=1)
        try:
            with pytest.raises(WorkerCrashedError):
                await pool.run(os._exit, 1)  # simula un worker que muere (p. ej. OOM)
            return await pool.run(math.sqrt, 16)
        finally:
            pool.close()

    assert asyncio.run(scenario()) == 4.0
