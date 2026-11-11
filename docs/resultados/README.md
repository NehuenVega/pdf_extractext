# Resultados de las pruebas de carga

Acá van los resultados de k6 y Vegeta que se citan en el informe
(`docs/INFORME.md`, sección 6.3). Los crudos se generan en
`tests/stress/results/`, que git ignora porque se regenera en cada corrida.

Después de cada corrida que se quiera conservar:

1. Copiar a esta carpeta el JSON de k6 (`k6-spike-*.json`) y los `.json`,
   `.txt` y `.html` de Vegeta (el `.bin` y el `.csv` no hacen falta).
2. Correr `python scripts/compare_results.py --markdown` y pegar las tablas en
   el informe.
3. Anotar en el commit la configuración usada (variables de `.env`) y el
   hardware donde se midió.
