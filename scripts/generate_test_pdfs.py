"""Genera los 4 PDFs de prueba sustitutos en ``tests/stress/pdfs-sustitutos``.

La consigna pide usar la carpeta oficial de la cátedra (``tests/stress/pdfs``),
con archivos "de tamaño y densidad variable (desde livianos hasta PDFs con
gráficos/capas de ~9 MB)". Mientras no tengamos esa carpeta, este script crea
cuatro documentos con ese mismo perfil para poder desarrollar y medir:

    01-liviano.pdf          2 páginas de texto simple.
    02-mediano.pdf          30 páginas con títulos, listas y tablas.
    03-extenso.pdf          292 páginas de texto denso con índice (outline).
    04-graficos-capas.pdf   ~9 MB: texto + gráficos vectoriales + imágenes,
                            repartidos en capas opcionales (OCG).

Es determinístico (semilla fija): dos ejecuciones generan el mismo contenido,
así las mediciones del equipo son comparables entre sí.

Uso:
    python scripts/generate_test_pdfs.py [--output tests/stress/pdfs-sustitutos]
"""

from __future__ import annotations

import argparse
import math
import random
from pathlib import Path

import pymupdf

SEED = 2026
A4 = pymupdf.paper_rect("a4")
MARGIN = 50
TEXT_AREA = pymupdf.Rect(MARGIN, MARGIN, A4.width - MARGIN, A4.height - MARGIN)

# Vocabulario para armar texto "realista" en castellano. No hace falta que
# tenga sentido: lo que importa para la extracción es la densidad de texto.
VOCABULARY = """
sistema servicio arquitectura microservicio contenedor réplica balanceo
latencia rendimiento concurrencia proceso hilo memoria procesador cola
petición respuesta documento página texto extracción formato archivo red
prueba carga estrés métrica percentil error tiempo usuario cliente servidor
configuración variable entorno registro despliegue imagen volumen puerto
protocolo cabecera cuerpo datos estructura módulo función parámetro valor
resultado análisis diseño decisión criterio calidad código mantenimiento
el la los las un una de del con sin para por sobre entre desde hasta cuando
mientras porque aunque además también entonces luego según durante bajo
permite define establece mejora reduce aumenta procesa devuelve recibe mide
compara evalúa controla limita distribuye escala optimiza garantiza valida
rápido lento estable eficiente robusto simple complejo distribuido seguro
"""
WORDS = VOCABULARY.split()


def sentence(rng: random.Random) -> str:
    """Devuelve una oración de 8 a 20 palabras, con mayúscula y punto final."""
    words = rng.choices(WORDS, k=rng.randint(8, 20))
    return " ".join(words).capitalize() + "."


def paragraph(rng: random.Random, sentences: int) -> str:
    return " ".join(sentence(rng) for _ in range(sentences))


def html_list(rng: random.Random, items: int) -> str:
    return "<ul>" + "".join(f"<li>{sentence(rng)}</li>" for _ in range(items)) + "</ul>"


def html_table(rng: random.Random, rows: int) -> str:
    header = "<tr><th>Escenario</th><th>Peticiones</th><th>P95 (s)</th></tr>"
    body = "".join(
        f"<tr><td>{rng.choice(WORDS).capitalize()}</td>"
        f"<td>{rng.randint(100, 5000)}</td>"
        f"<td>{rng.uniform(0.1, 9.9):.2f}</td></tr>"
        for _ in range(rows)
    )
    return f"<table border='1'>{header}{body}</table>"


def add_html_page(doc: pymupdf.Document, html: str, area: pymupdf.Rect = TEXT_AREA) -> pymupdf.Page:
    """Agrega una página A4 y le maqueta el HTML dentro del área indicada."""
    page = doc.new_page(width=A4.width, height=A4.height)
    # scale_low=0 permite achicar la letra si el bloque no entra: así cada
    # llamada produce exactamente una página y controlamos el page_count.
    page.insert_htmlbox(area, html, scale_low=0)
    return page


def save_reproducible(doc: pymupdf.Document, path: Path) -> None:
    """Guarda sin fechas ni IDs aleatorios: misma entrada, mismos bytes."""
    doc.save(path, garbage=4, deflate=True, no_new_id=True, reproducible=True)


def build_light(output: Path, rng: random.Random) -> None:
    doc = pymupdf.open()
    toc = []
    for number in range(1, 3):
        title = f"Sección {number}: {sentence(rng)[:40]}"
        toc.append([1, title, number])
        add_html_page(doc, f"<h1>{title}</h1>" + "".join(f"<p>{paragraph(rng, 4)}</p>" for _ in range(4)))
    doc.set_toc(toc)
    save_reproducible(doc, output / "01-liviano.pdf")


def build_medium(output: Path, rng: random.Random) -> None:
    doc = pymupdf.open()
    toc = []
    for number in range(1, 31):
        title = f"Capítulo {number}"
        toc.append([1, title, number])
        blocks = [
            f"<h1>{title}</h1>",
            f"<p>{paragraph(rng, 5)}</p>",
            f"<h2>{sentence(rng)[:50]}</h2>",
            html_list(rng, 4) if number % 2 else html_table(rng, 6),
            f"<p>{paragraph(rng, 5)}</p>",
        ]
        add_html_page(doc, "".join(blocks))
    doc.set_toc(toc)
    save_reproducible(doc, output / "02-mediano.pdf")


def build_long(output: Path, rng: random.Random) -> None:
    """292 páginas: el mismo page_count que muestra el ejemplo de la consigna."""
    doc = pymupdf.open()
    toc = []
    for number in range(1, 293):
        blocks = []
        # Un capítulo nuevo cada 12 páginas, con subtítulos intermedios.
        if number % 12 == 1:
            title = f"Capítulo {number // 12 + 1}"
            toc.append([1, title, number])
            blocks.append(f"<h1>{title}</h1>")
        elif number % 4 == 1:
            subtitle = sentence(rng)[:45]
            toc.append([2, subtitle, number])
            blocks.append(f"<h2>{subtitle}</h2>")
        blocks.extend(f"<p>{paragraph(rng, 4)}</p>" for _ in range(6))
        add_html_page(doc, "".join(blocks))
    doc.set_toc(toc)
    save_reproducible(doc, output / "03-extenso.pdf")


def noisy_jpeg(rng: random.Random, width: int, height: int) -> bytes:
    """JPEG con degradé + ruido: comprime poco, como una foto o un escaneo."""
    samples = bytearray(width * height * 3)
    noise = rng.randbytes(len(samples))
    for y in range(height):
        base = int(255 * y / height)
        for x in range(0, width * 3, 3):
            i = y * width * 3 + x
            samples[i] = (base + noise[i] % 64) % 256
            samples[i + 1] = (x // 3 * 255 // width + noise[i + 1] % 64) % 256
            samples[i + 2] = noise[i + 2]
    pixmap = pymupdf.Pixmap(pymupdf.csRGB, width, height, bytes(samples), False)
    return pixmap.tobytes("jpeg", jpg_quality=85)


def draw_line_chart(page: pymupdf.Page, rng: random.Random, area: pymupdf.Rect, layer: int) -> None:
    """Gráfico de líneas con muchos puntos + grilla: mucho trabajo vectorial."""
    shape = page.new_shape()
    for i in range(1, 20):
        y = area.y0 + area.height * i / 20
        shape.draw_line((area.x0, y), (area.x1, y))
    shape.finish(width=0.2, color=(0.8, 0.8, 0.8), oc=layer)

    for series, color in enumerate([(0.1, 0.3, 0.8), (0.8, 0.2, 0.2), (0.1, 0.6, 0.3)]):
        phase = rng.uniform(0, math.pi)
        points = [
            pymupdf.Point(
                area.x0 + area.width * k / 1500,
                area.y0 + area.height * (0.5 + 0.35 * math.sin(k / 60 + phase + series) + rng.uniform(-0.05, 0.05)),
            )
            for k in range(1500)
        ]
        shape.draw_polyline(points)
        shape.finish(width=0.6, color=color, closePath=False, oc=layer)
    shape.commit()


def draw_blueprint(page: pymupdf.Page, rng: random.Random, layer: int) -> None:
    """Capa oculta con miles de rectángulos chicos (tipo plano técnico)."""
    shape = page.new_shape()
    for _ in range(2500):
        x, y = rng.uniform(0, A4.width), rng.uniform(0, A4.height)
        shape.draw_rect(pymupdf.Rect(x, y, x + rng.uniform(2, 12), y + rng.uniform(2, 12)))
    shape.finish(width=0.3, color=(0.4, 0.4, 0.4), oc=layer)
    shape.commit()


def build_graphics_and_layers(output: Path, rng: random.Random) -> None:
    doc = pymupdf.open()
    charts_layer = doc.add_ocg("Gráficos", on=True)
    images_layer = doc.add_ocg("Imágenes", on=True)
    blueprint_layer = doc.add_ocg("Plano técnico", on=False)
    toc = []
    for number in range(1, 41):
        title = f"Informe de métricas {number}"
        toc.append([1, title, number])
        html = f"<h1>{title}</h1><p>{paragraph(rng, 5)}</p><p>{paragraph(rng, 4)}</p>"
        page = add_html_page(doc, html, pymupdf.Rect(MARGIN, MARGIN, A4.width - MARGIN, 300))
        page.insert_image(pymupdf.Rect(MARGIN, 310, 300, 500), stream=noisy_jpeg(rng, 448, 336), oc=images_layer)
        draw_line_chart(page, rng, pymupdf.Rect(MARGIN, 520, A4.width - MARGIN, 790), charts_layer)
        draw_blueprint(page, rng, blueprint_layer)
    doc.set_toc(toc)
    save_reproducible(doc, output / "04-graficos-capas.pdf")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", type=Path, default=Path("tests/stress/pdfs-sustitutos"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    # Cada documento usa su propio generador con semilla derivada, así
    # regenerar uno solo no altera el contenido de los demás.
    builders = [build_light, build_medium, build_long, build_graphics_and_layers]
    for index, build in enumerate(builders):
        build(args.output, random.Random(SEED + index))

    for pdf in sorted(args.output.glob("*.pdf")):
        with pymupdf.open(pdf) as doc:
            print(f"{pdf.name:<26} {pdf.stat().st_size / 1_048_576:6.2f} MB  {doc.page_count:4d} páginas")


if __name__ == "__main__":
    main()
