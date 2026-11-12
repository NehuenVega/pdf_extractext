# PDFs de prueba

Son los 4 PDFs oficiales de la cátedra, los mismos que usa el benchmark del
profesor (su `test_carga.txt` para Vegeta y su script de k6). Se tomaron de su
repositorio público.

| Archivo | Tamaño | Páginas | Extracción (1 proceso, sin carga) |
|---|---:|---:|---:|
| `2020-Scrum-Guide-Spanish-Latin-South-American.pdf` | 312 KB | 16 | 42 ms |
| `Filosofia Lean.pdf` | 652 KB | 42 | 149 ms |
| `scrum_manager_historias_usuario.pdf` | 3,7 MB | 62 | 130 ms |
| `Essential-Kanban-Condensed-Spanish.pdf` | 8,7 MB | 90 | 223 ms |

Los scripts de k6 y Vegeta toman todos los `*.pdf` de esta carpeta, sin
importar sus nombres.

Durante el desarrollo, antes de tener estos archivos, usamos 4 PDFs sustitutos
que se pueden regenerar con `python scripts/generate_test_pdfs.py --output
<carpeta>` (reproducibles byte a byte). Los resultados con esos PDFs están en
`docs/resultados/sustitutos/` y en la sección 6.4 del informe.
