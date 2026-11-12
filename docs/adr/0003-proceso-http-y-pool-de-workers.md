# ADR-0003: Separar el runtime HTTP de la extracción con un pool de procesos

## Estado
Aceptado

## Fecha
2026-10-07

## Contexto

La consigna (punto 5.4) sugiere "separar el runtime HTTP de la ejecución del
algoritmo de extracción". Extraer un PDF ocupa la CPU entre 5 y 470 ms. Si eso
pasa en el event loop de uvicorn, durante ese tiempo la réplica no acepta
conexiones ni responde `/health`, y HAProxy la marcaría como caída.

En CPython el GIL impide que dos hilos ejecuten código Python a la vez, y
PyMuPDF no está pensado para usarse desde varios hilos.

## Decisión

- Un proceso uvicorn por réplica con un único event loop (Starlette), que solo
  recibe pedidos, controla la admisión y responde.
- Un `ProcessPoolExecutor` (contexto `spawn`) con `EXTRACTION_WORKERS`
  procesos (1 por defecto, uno por CPU) que hacen la extracción.
- Los workers se levantan y calientan antes de aceptar tráfico, así el primer
  pedido no paga el arranque ni la carga de MuPDF.
- El worker devuelve la respuesta **ya serializada en JSON**: el proceso HTTP no
  gasta CPU en convertir textos de cientos de KB, solo reenvía bytes.
- Si un worker muere (por ejemplo, el kernel lo mata por memoria), el pool se
  reemplaza y el pedido recibe un 500 explícito en lugar de dejar la réplica
  inutilizada.
- La caché de MuPDF **no** se vacía entre documentos: en 200 extracciones
  seguidas la memoria del worker quedó estable en ~63 MB sin hacerlo, y
  vaciarla (`store_shrink`) hacía cada extracción ~7 % más lenta.

## Alternativas consideradas

### Extraer en el event loop
- En contra: bloquea health checks y nuevas conexiones. Rechazada.

### Hilos (`asyncio.to_thread`)
- En contra: el GIL serializa el trabajo Python y PyMuPDF no es seguro entre
  hilos. Rechazada.

### Varios procesos uvicorn por réplica (`--workers N`)
- En contra: cada proceso tendría su propia cola y su propio control de
  admisión; con 1 CPU por réplica no aporta paralelismo real. Rechazada.

### Memoria compartida para pasar el PDF al worker (evitar el pickle)
- Medido: serializar y deserializar con pickle el PDF de 9,6 MB cuesta ~8 ms,
  contra ~200 ms de extracción (≈4 %). No justifica manejar el ciclo de vida
  de un bloque de memoria compartida. Rechazada por simplicidad.

## Consecuencias

- La réplica sigue respondiendo `/health` y rechazando con 503 aunque el worker
  esté ocupado.
- Pasar el PDF entre procesos implica una copia (≈4 % del tiempo de
  extracción en el peor caso, el PDF de 9,6 MB). Dentro del worker no hay más
  copias: MuPDF lee directo de los bytes recibidos.
- Cada réplica usa ~65 MB por worker (pico medido), lejos del límite de 1 GB.
