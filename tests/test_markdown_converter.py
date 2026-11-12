"""Tests de la conversión de líneas con estilo a Markdown (lógica pura)."""

from App.infrastructure.markdown.converter import to_markdown
from App.infrastructure.markdown.reader import TextLine


def line(text: str, size: float = 12, bold: bool = False) -> TextLine:
    return TextLine(text=text, size=size, bold=bold)


BODY = "Texto de cuerpo suficientemente largo para que este tamaño sea el dominante del documento."


def test_largest_heading_size_becomes_level_one():
    blocks = [(line("Título", size=24),), (line(BODY),)]

    assert to_markdown(blocks).startswith("# Título\n\n")


def test_heading_levels_follow_the_size_ranking_of_the_document():
    blocks = [
        (line("Capítulo", size=20),),
        (line("Sección", size=16),),
        (line("Subsección", size=14),),
        (line(BODY),),
    ]

    assert to_markdown(blocks).splitlines()[::2] == ["# Capítulo", "## Sección", "### Subsección", BODY]


def test_levels_are_relative_to_the_body_size_not_absolute():
    small_document = [(line("Título", size=12),), (line(BODY, size=9),)]

    assert to_markdown(small_document).startswith("# Título")


def test_text_slightly_bigger_than_body_is_not_a_heading():
    blocks = [(line("Apenas más grande", size=12.5),), (line(BODY),)]

    assert to_markdown(blocks).startswith("Apenas más grande")


def test_long_paragraph_in_big_font_is_not_a_heading():
    long_quote = "Una cita destacada muy larga. " * 10
    blocks = [(line(long_quote.strip(), size=18),), (line(BODY), line(BODY), line(BODY))]

    assert not to_markdown(blocks).startswith("#")


def test_lines_of_a_paragraph_are_joined_with_spaces():
    blocks = [(line("primera línea del párrafo"), line("y su continuación."))]

    assert to_markdown(blocks) == "primera línea del párrafo y su continuación."


def test_paragraphs_are_separated_by_a_blank_line():
    blocks = [(line("Primer párrafo."),), (line("Segundo párrafo."),)]

    assert to_markdown(blocks) == "Primer párrafo.\n\nSegundo párrafo."


def test_heading_and_paragraph_in_the_same_block_are_split():
    blocks = [(line("Contexto", size=18), line(BODY), line(BODY))]

    assert to_markdown(blocks) == f"# Contexto\n\n{BODY} {BODY}"


def test_bullets_become_markdown_list_items():
    blocks = [(line("• Primer ítem"), line("● Segundo ítem"), line("▪ Tercer ítem"))]

    assert to_markdown(blocks) == "- Primer ítem\n- Segundo ítem\n- Tercer ítem"


def test_wrapped_list_item_is_joined_with_its_continuation():
    blocks = [(line("• Un ítem que no entró"), line("en una sola línea"), line("• Otro ítem"))]

    assert to_markdown(blocks) == "- Un ítem que no entró en una sola línea\n- Otro ítem"


def test_short_bold_line_is_rendered_in_bold():
    blocks = [(line("Nota importante", bold=True),), (line(BODY),)]

    assert to_markdown(blocks).startswith("**Nota importante**")


def test_invisible_characters_are_removed():
    blocks = [(line("●\u200b Endpoint\u00a0obligatorio"),)]

    assert to_markdown(blocks) == "- Endpoint obligatorio"


def test_paragraph_starting_with_hash_is_escaped():
    blocks = [(line("#1 en ventas"),)]

    assert to_markdown(blocks) == "\\#1 en ventas"


def test_text_with_zero_font_size_produces_no_headings():
    blocks = [(line("Texto invisible", size=0),), (line("Otro", size=0),)]

    assert to_markdown(blocks) == "Texto invisible\n\nOtro"


def test_empty_document_produces_empty_markdown():
    assert to_markdown([]) == ""
