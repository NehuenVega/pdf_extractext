"""Conversión de bloques de texto con estilo a Markdown.

Es lógica pura (no conoce MuPDF ni HTTP), así que se testea con datos armados
a mano. Las reglas son heurísticas simples, elegidas para ser baratas y
fáciles de explicar:

- **Tamaño de cuerpo:** el tamaño de letra que más caracteres ocupa en el
  documento.
- **Título:** párrafo corto con letra al menos 15 % más grande que el cuerpo.
  El nivel (``#``, ``##``, ...) sale del ranking de tamaños de título del
  propio documento: el más grande es ``#``. Así funciona igual con un PDF de
  cuerpo 10 pt que con uno de cuerpo 12 pt.
- **Negrita:** línea suelta y corta, toda en negrita, que no es título.
- **Lista:** línea que empieza con una viñeta (•, ●, ▪, –, ...) → ``- ``.
- Todo lo demás es un párrafo; sus líneas se unen con espacios.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from itertools import groupby

from App.infrastructure.markdown.reader import Block

# Cuánto más grande que el cuerpo tiene que ser la letra para considerar
# título a un párrafo. 15 % separa bien 12 pt (cuerpo) de 14 pt (subtítulo).
HEADING_MIN_SIZE_RATIO = 1.15

# Un título real es corto: si un párrafo grande tiene más que esto, es texto
# destacado (por ejemplo, una cita en letra grande) y no un título.
HEADING_MAX_LINES = 3
HEADING_MAX_CHARS = 200

# Largo máximo de una línea en negrita para mostrarla como **negrita**.
BOLD_MAX_CHARS = 120

MAX_HEADING_LEVEL = 6

BULLETS = frozenset("•●○◦▪▫■□‣⁃∙·–—*-")

# Caracteres invisibles que algunos editores (Google Docs, Word) meten en el
# texto y ensucian el Markdown: espacio de ancho cero, guion opcional y BOM.
# El espacio duro (no separable) se normaliza a un espacio común.
_INVISIBLE_CHARS = ("\u200b", "\u00ad", "\ufeff")
_NON_BREAKING_SPACE = "\u00a0"


@dataclass(frozen=True, slots=True)
class _Paragraph:
    """Líneas consecutivas de un bloque que comparten tamaño de letra."""

    lines: tuple[str, ...]
    size: float
    bold: bool

    @property
    def length(self) -> int:
        return sum(len(line) for line in self.lines)


def to_markdown(blocks: Iterable[Block]) -> str:
    """Convierte los bloques de un documento (en orden de lectura) a Markdown."""
    paragraphs = [paragraph for block in blocks for paragraph in _split_by_font_size(block)]
    body_size = _body_font_size(paragraphs)
    heading_levels = _heading_levels(paragraphs, body_size)

    rendered = (_render(paragraph, body_size, heading_levels) for paragraph in paragraphs)
    return "\n\n".join(text for text in rendered if text)


def _split_by_font_size(block: Block) -> list[_Paragraph]:
    """Separa un bloque cuando cambia el tamaño de letra entre líneas.

    MuPDF a veces junta en un mismo bloque un título y el párrafo que le
    sigue; separarlos por tamaño evita que el párrafo termine como título.
    """
    paragraphs = []
    for size, group in groupby(block, key=lambda line: _round_size(line.size)):
        lines = list(group)
        texts = tuple(text for line in lines if (text := _clean(line.text)))
        if texts:
            paragraphs.append(_Paragraph(lines=texts, size=size, bold=all(line.bold for line in lines)))
    return paragraphs


def _clean(text: str) -> str:
    """Quita caracteres invisibles y espacios sobrantes de una línea.

    Se usa str.replace y no str.translate: medimos que translate con tabla
    es ~30 veces más lento (85 ms vs. 3 ms en un PDF de 292 páginas) porque
    consulta un diccionario por cada carácter.
    """
    for char in _INVISIBLE_CHARS:
        text = text.replace(char, "")
    return text.replace(_NON_BREAKING_SPACE, " ").strip()


def _round_size(size: float) -> float:
    """Redondea a medio punto: 11.98 pt y 12.02 pt son el mismo tamaño."""
    return round(size * 2) / 2


def _body_font_size(paragraphs: list[_Paragraph]) -> float:
    characters_by_size: Counter[float] = Counter()
    for paragraph in paragraphs:
        characters_by_size[paragraph.size] += paragraph.length
    if not characters_by_size:
        return 0.0
    return characters_by_size.most_common(1)[0][0]


def _looks_like_heading(paragraph: _Paragraph, body_size: float) -> bool:
    # Sin un tamaño de cuerpo válido (texto de tamaño 0, o ningún texto) no
    # hay contra qué comparar: no se marcan títulos.
    return (
        body_size > 0
        and paragraph.size >= body_size * HEADING_MIN_SIZE_RATIO
        and len(paragraph.lines) <= HEADING_MAX_LINES
        and paragraph.length <= HEADING_MAX_CHARS
    )


def _heading_levels(paragraphs: list[_Paragraph], body_size: float) -> dict[float, int]:
    """Asigna un nivel de título a cada tamaño de letra usado en títulos."""
    heading_sizes = sorted(
        {paragraph.size for paragraph in paragraphs if _looks_like_heading(paragraph, body_size)},
        reverse=True,
    )
    return {size: min(level, MAX_HEADING_LEVEL) for level, size in enumerate(heading_sizes, start=1)}


def _render(paragraph: _Paragraph, body_size: float, heading_levels: dict[float, int]) -> str:
    if _looks_like_heading(paragraph, body_size):
        return "#" * heading_levels[paragraph.size] + " " + " ".join(paragraph.lines)

    if paragraph.bold and len(paragraph.lines) == 1 and paragraph.length <= BOLD_MAX_CHARS:
        return f"**{paragraph.lines[0]}**"

    return _render_body(paragraph.lines)


def _render_body(lines: tuple[str, ...]) -> str:
    """Une las líneas de un párrafo y convierte las viñetas en ítems de lista.

    Una línea sin viñeta que sigue a un ítem es la continuación de ese ítem
    (el texto del ítem no entró en una sola línea del PDF).
    """
    output: list[str] = []
    for line in lines:
        if _starts_with_bullet(line):
            output.append("- " + line[1:].strip())
        elif output:
            output[-1] += " " + line
        else:
            output.append(_escape_block_start(line))
    return "\n".join(output)


def _starts_with_bullet(line: str) -> bool:
    return len(line) > 1 and line[0] in BULLETS and line[1].isspace()


def _escape_block_start(line: str) -> str:
    """Evita que un párrafo que empieza con '#' o '>' se lea como título o cita."""
    return "\\" + line if line[0] in "#>" else line
