"""Compara los resultados de k6 y Vegeta con el benchmark del profesor.

Lee los archivos que dejan las pruebas en ``tests/stress/results`` (por
defecto, los más recientes) y muestra una tabla por prueba con nuestras
métricas, las del profesor y si las superamos.

Uso:
    python scripts/compare_results.py              # últimos resultados
    python scripts/compare_results.py --markdown   # tablas para el informe
    python scripts/compare_results.py --k6 archivo.json --vegeta archivo.json
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

RESULTS_DIR = Path("tests/stress/results")


@dataclass(frozen=True, slots=True)
class Metric:
    name: str
    ours: float
    professor: float
    unit: str  # "req", "req/s", "%", "s"
    higher_is_better: bool

    @property
    def better(self) -> bool:
        if self.higher_is_better:
            return self.ours > self.professor
        return self.ours < self.professor or (self.ours == self.professor == 0)

    def format(self, value: float) -> str:
        if math.isnan(value):
            return "-"
        match self.unit:
            case "req":
                return f"{value:.0f}"
            case "%":
                return f"{value:.2f} %"
            case "s":
                return f"{value:.2f} s"
            case _:
                return f"{value:.2f}"


def k6_metrics(summary: dict) -> list[Metric]:
    """Métricas de la prueba spike a partir del JSON de handleSummary de k6."""
    metrics = summary["metrics"]
    requests = metrics["http_reqs"]["values"]
    duration = metrics["http_req_duration"]["values"]
    return [
        Metric("Peticiones procesadas", requests["count"], 1037, "req", higher_is_better=True),
        Metric("Throughput sostenido", requests["rate"], 25.35, "req/s", higher_is_better=True),
        Metric("Tasa de error", metrics["http_req_failed"]["values"]["rate"] * 100, 0.0, "%", higher_is_better=False),
        Metric("Latencia p50", duration["med"] / 1000, 1.88, "s", higher_is_better=False),
        Metric("Latencia p90", duration["p(90)"] / 1000, 7.83, "s", higher_is_better=False),
        Metric("Latencia p95", duration["p(95)"] / 1000, 8.80, "s", higher_is_better=False),
        Metric("Latencia máxima", duration["max"] / 1000, 13.94, "s", higher_is_better=False),
    ]


def vegeta_metrics(report: dict, requests: list[tuple[int, int]]) -> list[Metric]:
    """Métricas de la prueba fija a partir del reporte JSON de Vegeta y de
    la lista (código, latencia en ns) de cada pedido."""
    status_codes = {int(code): count for code, count in report["status_codes"].items()}
    successes = sum(count for code, count in status_codes.items() if 200 <= code < 300)
    success_latencies = [latency for code, latency in requests if 200 <= code < 300]
    return [
        Metric("Throughput efectivo completado", report["throughput"], 16.65, "req/s", higher_is_better=True),
        Metric("Peticiones exitosas", successes, 998, "req", higher_is_better=True),
        Metric("Tasa de éxito", report["success"] * 100, 66.53, "%", higher_is_better=True),
        Metric("Timeouts de cliente (código 0)", status_codes.get(0, 0), 501, "req", higher_is_better=False),
        Metric("Latencia p50 (todas)", report["latencies"]["50th"] / 1e9, 14.89, "s", higher_is_better=False),
        # El profesor no informa este valor; lo agregamos porque la mediana de
        # Vegeta mezcla éxitos y rechazos (un 503 inmediato la "mejora").
        Metric("Latencia p50 (solo exitosas)", median(success_latencies) / 1e9, math.nan, "s", higher_is_better=False),
    ]


def median(values: Iterable[float]) -> float:
    """Mediana exacta; NaN si no hay valores."""
    ordered = sorted(values)
    if not ordered:
        return math.nan
    middle = len(ordered) // 2
    return ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2


def read_vegeta_csv(path: Path) -> list[tuple[int, int]]:
    """Lee (código, latencia en ns) de cada pedido del CSV de ``vegeta encode``.

    Columnas: timestamp, código, latencia (ns), bytes enviados, bytes
    recibidos, error, body, ataque, secuencia, método, URL, encabezados.
    """
    with path.open(newline="", encoding="utf-8") as file:
        return [(int(row[1]), int(row[2])) for row in csv.reader(file) if row]


def render(title: str, metrics: list[Metric], markdown: bool) -> str:
    if markdown:
        lines = [f"**{title}**", "", "| Métrica | Nuestro | Profesor | ¿Mejor? |", "|---|---:|---:|:---:|"]
        lines += [
            f"| {m.name} | {m.format(m.ours)} | {m.format(m.professor)} | "
            f"{'-' if math.isnan(m.professor) else ('✅' if m.better else '❌')} |"
            for m in metrics
        ]
    else:
        lines = [title, "", f"{'Métrica':<32}{'Nuestro':>12}{'Profesor':>12}   Mejor", "-" * 64]
        lines += [
            f"{m.name:<32}{m.format(m.ours):>12}{m.format(m.professor):>12}   "
            f"{'-' if math.isnan(m.professor) else ('sí' if m.better else 'no')}"
            for m in metrics
        ]
    return "\n".join(lines) + "\n"


def latest(pattern: str) -> Path | None:
    candidates = sorted(RESULTS_DIR.glob(pattern), key=lambda path: path.stat().st_mtime)
    return candidates[-1] if candidates else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--k6", type=Path, help="JSON de resumen de k6 (por defecto, el más reciente)")
    parser.add_argument("--vegeta", type=Path, help="Reporte JSON de Vegeta (por defecto, el más reciente)")
    parser.add_argument("--markdown", action="store_true", help="Imprime tablas en formato Markdown")
    args = parser.parse_args()

    k6_file = args.k6 or latest("k6-spike-*.json")
    vegeta_file = args.vegeta or latest("vegeta-*.json")
    if not k6_file and not vegeta_file:
        sys.exit(f"No hay resultados en {RESULTS_DIR}. Corré primero las pruebas (ver README).")

    if k6_file:
        summary = json.loads(k6_file.read_text(encoding="utf-8"))
        print(render(f"Spike k6 — {k6_file.name}", k6_metrics(summary), args.markdown))
    if vegeta_file:
        report = json.loads(vegeta_file.read_text(encoding="utf-8"))
        csv_file = vegeta_file.with_suffix(".csv")
        requests = read_vegeta_csv(csv_file) if csv_file.exists() else []
        print(render(f"Vegeta — {vegeta_file.name}", vegeta_metrics(report, requests), args.markdown))


if __name__ == "__main__":
    main()
