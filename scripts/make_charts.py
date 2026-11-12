"""Genera los gráficos del informe a partir de los datos de investigación.

Entradas:
    docs/investigacion/benchmark_extraccion.json  (scripts/benchmark_extractors.py)
    scripts/simulate_queues.py                     (se re-simula la prueba de Vegeta)
Salidas:
    docs/img/benchmark-motores.png
    docs/img/vegeta-simulado.png

Criterios de diseño: un solo eje por gráfico, marcas finas, grilla tenue, el
texto siempre en tinta neutra (nunca del color de la serie) y cada gráfico
con su tabla equivalente en el informe. Las dos series se distinguen también
con daltonismo (diferencia de color ΔE 24,7 entre azul y naranja).

Uso:
    python scripts/make_charts.py
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # sin ventana: solo archivos
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter
from simulate_queues import (
    CLIENT_TIMEOUT,
    OK,
    OVERLOADED,
    CentralQueue,
    ProcessorSharing,
    Request,
    Simulation,
)

ROOT = Path(__file__).resolve().parent.parent
IMAGES = ROOT / "docs/img"

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
ACCENT = "#2a78d6"  # serie principal (azul)
CONTEXT = "#b4b2a9"  # resto de las barras (énfasis: gris)
CRITICAL = "#d03b3b"  # estado: pedido fallido (siempre con etiqueta)
WARNING = "#eb6834"  # pedido rechazado con 503 (siempre con etiqueta)

plt.rcParams.update(
    {
        "font.family": ["Segoe UI", "DejaVu Sans"],
        "font.size": 10,
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "axes.edgecolor": AXIS,
        "axes.labelcolor": INK_SECONDARY,
        "axes.titlecolor": INK,
        "axes.titlesize": 12,
        "axes.titleweight": "semibold",
        "axes.titlelocation": "left",
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "xtick.labelcolor": INK_SECONDARY,
        "ytick.labelcolor": INK_SECONDARY,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "legend.frameon": False,
        "legend.labelcolor": INK_SECONDARY,
    }
)


def human_time(milliseconds: float) -> str:
    return f"{milliseconds / 1000:.1f} s" if milliseconds >= 1000 else f"{milliseconds:.0f} ms"


def benchmark_chart() -> Path:
    """Tiempo total para extraer los 4 PDFs de prueba una vez, por motor."""
    data = json.loads((ROOT / "docs/investigacion/benchmark_extraccion.json").read_text(encoding="utf-8"))
    totals: dict[str, float] = {}
    labels: dict[str, str] = {}
    for result in data["results"]:
        totals[result["engine"]] = totals.get(result["engine"], 0.0) + result["median_s"] * 1000
        labels[result["engine"]] = result["label"]

    engines = sorted(totals, key=totals.get, reverse=True)  # el más rápido queda arriba
    figure, axes = plt.subplots(figsize=(9, 4.6))
    colors = [ACCENT if engine == "nuestro" else CONTEXT for engine in engines]
    axes.barh([labels[e] for e in engines], [totals[e] for e in engines], height=0.55, color=colors)
    axes.set_xscale("log")
    axes.grid(axis="y", visible=False)
    axes.tick_params(axis="y", length=0)
    for row, engine in enumerate(engines):
        axes.text(totals[engine] * 1.12, row, human_time(totals[engine]), va="center", color=INK, fontsize=9)
    axes.set_xlim(right=max(totals.values()) * 4)
    axes.xaxis.set_major_formatter(FuncFormatter(lambda value, _: human_time(value)))
    axes.set_xlabel("Tiempo total para extraer los 4 PDFs de prueba (escala logarítmica)")
    axes.set_title("Markdown al mismo costo que el texto plano", loc="left")
    figure.tight_layout()
    return _save(figure, "benchmark-motores.png")


def vegeta_chart() -> Path:
    """Latencia de cada pedido de Vegeta según cuándo se envió (simulado)."""
    pdfs = [
        Request(work, size)
        for work, size in zip([0.005, 0.035, 0.464, 0.199], [91, 144, 720, 9828], strict=True)
        for size in [size * 1024]
    ]
    architectures = {
        "Sin backpressure (procesador compartido)": ProcessorSharing(5),
        "Cola FIFO central, espera máxima 25 s": CentralQueue(5, queue_timeout_s=25),
    }
    series = [
        (OK, ACCENT, "Respuesta 200"),
        (CLIENT_TIMEOUT, CRITICAL, "Timeout del cliente (30 s)"),
        (OVERLOADED, WARNING, "Descartado con 503"),
    ]
    figure, panels = plt.subplots(1, 2, figsize=(10, 4.6), sharey=True)
    for panel, (title, policy) in zip(panels, architectures.items(), strict=True):
        simulation = Simulation(policy, client_timeout=30.0)
        for i in range(1500):
            simulation.schedule_arrival(i / 50, pdfs[i % len(pdfs)])
        outcomes = simulation.run()

        counts = []
        for code, color, label in series:
            points = [(o.arrival, o.latency) for o in outcomes if o.code == code]
            counts.append(f"{len(points)} {label.split(' (')[0].lower()}")
            if points:
                xs, ys = zip(*points, strict=True)
                panel.scatter(xs, ys, s=6, color=color, linewidths=0)
        panel.axhline(30, color=MUTED, linewidth=1)
        subtitle = " · ".join(counts)
        panel.set_title(f"{title}\n{subtitle}", fontsize=10, linespacing=1.6)
        panel.set_xlabel("Momento en que Vegeta envió el pedido (s)")
        panel.set_ylim(0, 33)
    panels[0].set_ylabel("Latencia (s)")
    handles = [Line2D([], [], marker="o", linestyle="", color=color, label=label) for _, color, label in series]
    handles.append(Line2D([], [], color=MUTED, label="Límite del cliente: 30 s"))
    figure.legend(handles=handles, loc="lower center", ncols=4, fontsize=9, bbox_to_anchor=(0.5, 0))
    figure.suptitle(
        "Vegeta a 50 req/s (simulado): sin control de admisión los pedidos vencen; con cola acotada, no",
        x=0.01,
        ha="left",
        fontsize=12,
        fontweight="semibold",
        color=INK,
    )
    figure.tight_layout(rect=(0, 0.07, 1, 1))
    return _save(figure, "vegeta-simulado.png")


def _save(figure: plt.Figure, name: str) -> Path:
    IMAGES.mkdir(parents=True, exist_ok=True)
    path = IMAGES / name
    figure.savefig(path, dpi=160)
    plt.close(figure)
    return path


def main() -> None:
    for path in (benchmark_chart(), vegeta_chart()):
        print(f"Generado {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
