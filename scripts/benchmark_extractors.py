"""Compara motores de extracción de texto de PDF (evidencia del ADR-0001).

Para cada combinación motor × PDF se lanza un subproceso nuevo que importa la
librería, hace una extracción de calentamiento y mide varias extracciones.
Usar un proceso por medición evita que la memoria o las cachés de una prueba
contaminen la siguiente.

Se mide:
- tiempo por documento (mediana de las repeticiones),
- pico de memoria del proceso y cuánto creció respecto de antes de extraer,
- cantidad de caracteres extraídos (para notar si un motor "pierde" texto).

Uso:
    python scripts/benchmark_extractors.py
    python scripts/benchmark_extractors.py --engines pymupdf-texto nuestro --repeat 9
"""

from __future__ import annotations

import argparse
import io
import json
import statistics
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Un motor muy lento se mide una sola vez: repetir 150 s no aporta precisión.
SLOW_RUN_SECONDS = 5.0
MAX_MEASURE_SECONDS = 20.0


def _pymupdf4llm_default(pdf: bytes) -> str:
    import pymupdf
    import pymupdf4llm

    return pymupdf4llm.to_markdown(pymupdf.open(stream=pdf), show_progress=False)


def _pymupdf4llm_light(pdf: bytes) -> str:
    # Modo clásico de pymupdf4llm, sin análisis de layout, tablas ni gráficos:
    # la configuración más rápida posible de la librería.
    import pymupdf
    from pymupdf4llm.helpers import pymupdf_rag

    return pymupdf_rag.to_markdown(
        pymupdf.open(stream=pdf),
        show_progress=False,
        ignore_images=True,
        ignore_graphics=True,
        table_strategy=None,
    )


def _pdfplumber(pdf: bytes) -> str:
    import pdfplumber

    with pdfplumber.open(io.BytesIO(pdf)) as document:
        return "\n".join(page.extract_text() or "" for page in document.pages)


def _pypdf(pdf: bytes) -> str:
    from pypdf import PdfReader

    return "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(pdf)).pages)


def _pypdfium2(pdf: bytes) -> str:
    import pypdfium2

    document = pypdfium2.PdfDocument(pdf)
    return "\n".join(page.get_textpage().get_text_bounded() for page in document)


def _pymupdf_text(pdf: bytes) -> str:
    import pymupdf

    with pymupdf.open(stream=pdf) as document:
        return "\n".join(page.get_text() for page in document)


def _pymupdf_dict(pdf: bytes) -> str:
    # Alternativa descartada para obtener los tamaños de letra: get_text("dict")
    # arma un diccionario de Python por cada fragmento de texto.
    import pymupdf

    with pymupdf.open(stream=pdf) as document:
        return "\n".join(
            "".join(span["text"] for span in line["spans"])
            for page in document
            for block in page.get_text("dict")["blocks"]
            for line in block.get("lines", [])
        )


def _ours(pdf: bytes) -> str:
    sys.path.insert(0, str(ROOT))
    from App.infrastructure.markdown import extract_markdown

    return extract_markdown(pdf).content


ENGINES: dict[str, tuple[str, Callable[[bytes], str]]] = {
    "pymupdf4llm": ("pymupdf4llm (por defecto, Markdown)", _pymupdf4llm_default),
    "pymupdf4llm-liviano": ("pymupdf4llm (modo clásico liviano, Markdown)", _pymupdf4llm_light),
    "pdfplumber": ("pdfplumber (texto)", _pdfplumber),
    "pypdf": ("pypdf (texto)", _pypdf),
    "pypdfium2": ("pypdfium2 (texto)", _pypdfium2),
    "pymupdf-texto": ("PyMuPDF get_text (texto)", _pymupdf_text),
    "pymupdf-dict": ("PyMuPDF get_text('dict') (texto + tamaños)", _pymupdf_dict),
    "nuestro": ("Nuestro extractor (MuPDF JSON + Markdown)", _ours),
}


def peak_memory_bytes() -> int:
    """Pico de memoria residente del proceso actual."""
    if sys.platform == "win32":
        import psutil

        return psutil.Process().memory_info().peak_wset
    import resource

    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024  # Linux informa en KB


def current_memory_bytes() -> int:
    import psutil

    return psutil.Process().memory_info().rss


def measure(engine: str, pdf_path: Path, repeat: int) -> dict:
    """Corre dentro del subproceso: mide un motor sobre un PDF."""
    extract = ENGINES[engine][1]
    pdf = pdf_path.read_bytes()

    started = time.perf_counter()
    text = extract(pdf)  # calentamiento: carga la librería y sus cachés
    first_run = time.perf_counter() - started
    baseline = current_memory_bytes()

    durations = [first_run] if first_run >= SLOW_RUN_SECONDS else []
    while len(durations) < repeat and sum(durations) < MAX_MEASURE_SECONDS and first_run < SLOW_RUN_SECONDS:
        started = time.perf_counter()
        extract(pdf)
        durations.append(time.perf_counter() - started)

    return {
        "runs": len(durations),
        "median_s": statistics.median(durations),
        "min_s": min(durations),
        "peak_mb": peak_memory_bytes() / 1_048_576,
        "baseline_mb": baseline / 1_048_576,
        "chars": len(text),
    }


def run_in_subprocess(engine: str, pdf_path: Path, repeat: int) -> dict:
    command = [sys.executable, __file__, "--worker", engine, str(pdf_path), "--repeat", str(repeat)]
    completed = subprocess.run(command, capture_output=True, text=True, check=True, encoding="utf-8")
    return json.loads(completed.stdout.strip().splitlines()[-1])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pdfs", type=Path, default=ROOT / "tests/stress/pdfs")
    parser.add_argument("--engines", nargs="+", choices=ENGINES, default=list(ENGINES))
    parser.add_argument("--repeat", type=int, default=5)
    parser.add_argument("--output", type=Path, default=ROOT / "docs/investigacion/benchmark_extraccion.json")
    parser.add_argument("--worker", nargs=2, metavar=("MOTOR", "PDF"), help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.worker:
        engine, pdf_path = args.worker
        print(json.dumps(measure(engine, Path(pdf_path), args.repeat)))
        return

    results = []
    for pdf_path in sorted(args.pdfs.glob("*.pdf")):
        for engine in args.engines:
            result = {"engine": engine, "label": ENGINES[engine][0], "pdf": pdf_path.name}
            result |= run_in_subprocess(engine, pdf_path, args.repeat)
            results.append(result)
            print(
                f"{pdf_path.name:<24} {engine:<20} {result['median_s'] * 1000:10.1f} ms "
                f"({result['runs']} corridas)  pico {result['peak_mb']:6.0f} MB  {result['chars']:>8} caracteres",
                flush=True,
            )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    metadata = {"python": sys.version.split()[0], "platform": sys.platform, "repeat": args.repeat}
    # newline="\n": el JSON queda con fin de línea LF también en Windows.
    report = json.dumps({"metadata": metadata, "results": results}, indent=2)
    args.output.write_text(report, encoding="utf-8", newline="\n")
    print(f"\nResultados guardados en {args.output}")


if __name__ == "__main__":
    main()
