# ADR-0002: Balanceo y backpressure — HAProxy con cola central acotada y prioridad por tamaño

## Estado
Aceptado (revisado después de medir en Docker; la primera versión usaba FIFO pura)

## Fecha
2026-10-07

## Contexto

- Hasta 5 réplicas de 1 CPU cada una. Una réplica procesa un PDF por vez: dos
  extracciones simultáneas solo se reparten el mismo núcleo.
- Prueba k6 (modelo cerrado, 100 VUs): nunca hay más de 100 pedidos en vuelo.
- Prueba Vegeta (modelo abierto, 50 req/s durante 30 s, timeout de 30 s): si la
  capacidad es menor que 50 req/s, la cola crece sin parar. En el benchmark del
  profesor, 501 de 1.500 pedidos vencieron por timeout.
- Los PDFs tienen costos muy distintos (de 5 ms a 464 ms en nuestras mediciones).

Primero lo modelamos con un simulador de eventos discretos
(`scripts/simulate_queues.py`). Con los tiempos medidos fuera de Docker
(capacidad teórica de 28,4 req/s):

| Arquitectura (simulada) | k6 req/s | k6 p50 | k6 p95 | Vegeta éxito | Vegeta p50 |
|---|---:|---:|---:|---:|---:|
| Sin backpressure (todos a la vez) | 26,73 | 0,70 s | 9,28 s | 87,5 % | 3,61 s |
| Cola FIFO central, espera máx. 25 s | 27,90 | 3,22 s | 3,83 s | 100 % | 11,43 s |
| PDFs chicos siempre primero, 25 s | 26,55 | 0,98 s | 7,26 s | 100 % | 0,22 s |

Después lo medimos en Docker. La capacidad real resultó menor (~17 req/s,
porque 5 extracciones en paralelo se estorban por caché y memoria; ver informe
§4.5), y con esa capacidad el resultado cambió:

| Arquitectura (medida en Docker) | k6 req/s | k6 p50 | k6 p95 | Vegeta éxito | Vegeta p50 |
|---|---:|---:|---:|---:|---:|
| Profesor (su hardware) | 25,35 | 1,88 s | 8,80 s | 66,53 % | 14,89 s |
| Cola FIFO central, espera máx. 25 s | 15,75–19,48 | 4,67–5,82 s | 5,56–8,78 s | 64,2 % | 25,0 s |
| **PDFs chicos primero, 25 s** | **14,93–16,64** | **1,41–1,84 s** | 11,62–13,83 s | **80,4 %** | **0,95 s** |

Finalmente, con los **PDFs oficiales** de la cátedra (umbral recalibrado a
1 MB y k6 en binario, como el script del profesor):

| Configuración final, PDFs oficiales | k6 req/s | k6 p50 | k6 p95 | Vegeta éxito | Vegeta p50 |
|---|---:|---:|---:|---:|---:|
| PDFs < 1 MB primero, 25 s (mediana) | 25,45 | 0,77 s | 8,06 s | 98,5–100 % | 0,57–1,40 s |

## Decisión

**HAProxy** como reverse proxy, con:

- `maxconn 1` por réplica: cada réplica procesa un pedido por vez.
- Una **cola central** en el balanceador: el pedido que espera lo toma la
  primera réplica que se libera (`balance leastconn`).
- **Prioridad por tamaño:** los pedidos de menos de 1 MB
  (`HAPROXY_SMALL_PDF_BYTES`) salen de la cola antes que los grandes
  (`http-request set-priority-class`). Con `0` la cola es FIFO pura.
- `timeout queue 25s`: un pedido que espera más que eso recibe `503` +
  `Retry-After` **sin procesarse**. Quedan ~5 s para extraer antes del timeout
  de 30 s del cliente.
- Rechazo inmediato con 503 si la cola supera `HAPROXY_MAX_QUEUE` (1.000 por
  defecto: un tope de seguridad que no se alcanza en las pruebas).
- `abortonclose` (por defecto en HAProxy 3.4): si el cliente corta, su pedido
  sale de la cola sin gastar CPU.
- `tune.rcvbuf.client 131072`: acota el buffer de red de cada conexión. Sin
  él, con cientos de uploads grandes en cola, el kernel mató a HAProxy por
  memoria.

Todo es configurable por variables de entorno.

## Alternativas consideradas

### Sin control de admisión (lo que hace un servidor que acepta todo)
- En contra: bajo sobrecarga todos los pedidos se ralentizan juntos. Los
  grandes superan el timeout y el servidor los sigue procesando aunque el
  cliente ya se fue: es trabajo desperdiciado.
- El perfil del benchmark del profesor (p50 bajo con cola de latencias larga
  en k6, timeouts en Vegeta) se **parece cualitativamente** a este modelo. No
  lo reproducimos: sus PDFs y su hardware son otros, y en Vegeta la simulación
  da números distintos (87,5 % contra su 66,53 %).
- Rechazada.

### Cola FIFO pura (la decisión original)
- A favor: maximiza el throughput y acorta la cola de latencias en k6 (p95 de
  5,6 a 8,8 s medido).
- En contra: con la capacidad real, en Vegeta casi todos los pedidos esperan
  los 25 s completos (mediana 25,0 s) y el éxito queda en 64,2 %, **por debajo
  del profesor en las dos métricas que la consigna evalúa para esa prueba**.
- Queda disponible con `HAPROXY_SMALL_PDF_BYTES=0`.

### Round-robin "a ciegas" (Nginx OSS, `deploy.replicas` con el DNS de Docker)
- En contra: cada réplica tiene su propia cola, así que un PDF liviano puede
  quedar detrás de uno de 9 MB mientras otra réplica está libre. Nginx OSS no
  tiene cola con timeout (`queue` es solo de NGINX Plus).
- Rechazada.

### Traefik / Caddy (los que menciona la consigna como ejemplo)
- En contra: no tienen una cola central con timeout ni prioridades.
- Rechazadas: HAProxy es un reverse proxy "tipo Traefik/Caddy" con las
  funciones que necesitamos documentadas.

### `maxconn 2` / 2 extracciones por réplica
- Medido en Docker: 17,2 contra 17,1 req/s de promedio, dentro del ruido de
  ±10 % entre corridas. Con 1 CPU por réplica no suma.
- Rechazada.

### Rechazo temprano por largo de cola (`HAPROXY_MAX_QUEUE` bajo)
- Simulado con la capacidad real: baja la mediana, pero el éxito cae por
  debajo del 66,53 % del profesor.
- Rechazada (el tope queda alto, solo como seguridad).

## Consecuencias

- Ningún pedido aceptado espera más de 25 s en cola: no hay timeouts de
  cliente y los rechazos, si los hay, son 503 explícitos.
- En Vegeta se superan todas las métricas del profesor (informe §6.3).
- En k6, la ley de Little fija la latencia media en ~100/throughput. La
  prioridad baja la mediana y alarga la cola de los PDFs grandes. Con los PDFs
  oficiales el balance quedó favorable: p50 0,77 s y p95 8,06 s (el profesor:
  1,88 s y 8,80 s).
- El umbral de 1 MB está calibrado para los 4 PDFs oficiales (con 256 KB
  ninguno contaba como chico).
