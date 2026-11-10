// Prueba Spike con Grafana k6 (modelo cerrado).
//
// Perfil de la consigna: subida súbita a 100 VUs en 10 s, 20 s sostenidos a
// 100 VUs y rampa descendente de 10 s a 0 VUs.
//
// "Modelo cerrado": cada usuario virtual (VU) manda un pedido, espera la
// respuesta y recién entonces manda el siguiente. Nunca hay más de 100
// pedidos en vuelo, así que si el servicio se pone lento, la carga que recibe
// baja sola. (En Vegeta, modelo abierto, la carga no baja: ver vegeta/run.sh.)
//
// Variables de entorno (las completa run.sh):
//   BASE_URL      URL del servicio, por ejemplo http://proxy:8080
//   PDF_DIR       Carpeta con los PDFs de prueba
//   PDF_FILES     Nombres de los PDFs separados por coma (se rotan)
//   RESULTS_DIR   Carpeta donde se guarda el resumen en JSON
//   UPLOAD_MODE   "binary" (por defecto, como el script del profesor) o "multipart"

import http from 'k6/http';
import { check } from 'k6';
import exec from 'k6/execution';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8080';
const PDF_DIR = __ENV.PDF_DIR || '../pdfs';
const RESULTS_DIR = __ENV.RESULTS_DIR || '../results';
const UPLOAD_MODE = __ENV.UPLOAD_MODE || 'binary';

if (!__ENV.PDF_FILES) {
  throw new Error('Falta PDF_FILES (lista de PDFs separados por coma). Usá run.sh.');
}

// open() solo funciona en el contexto de inicialización: los PDFs se leen una
// vez por VU, antes de que empiece la prueba, y no durante la medición.
const PDFS = __ENV.PDF_FILES.split(',').map((name) => ({
  name,
  data: open(`${PDF_DIR}/${name}`, 'b'),
}));

// Métricas del profesor (consigna, "Benchmark de Referencia", prueba A).
const PROFESSOR = {
  requests: 1037,
  rate: 25.35,
  errorRate: 0.0,
  p50: 1880,
  p90: 7830,
  p95: 8800,
  max: 13940,
};

export const options = {
  scenarios: {
    spike: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '10s', target: 100 },
        { duration: '20s', target: 100 },
        { duration: '10s', target: 0 },
      ],
      gracefulRampDown: '30s',
    },
  },
  // Los umbrales son el benchmark del profesor: k6 marca con ✓/✗ si lo
  // superamos y termina con código de error si no.
  thresholds: {
    http_reqs: [`rate>${PROFESSOR.rate}`],
    http_req_failed: ['rate==0'],
    http_req_duration: [`med<${PROFESSOR.p50}`, `p(90)<${PROFESSOR.p90}`, `p(95)<${PROFESSOR.p95}`],
  },
  summaryTrendStats: ['avg', 'min', 'med', 'p(90)', 'p(95)', 'p(99)', 'max'],
};

export default function () {
  // Rotación determinística de los PDFs: cada VU arranca en uno distinto y
  // va avanzando en cada iteración, así todos los PDFs se piden por igual.
  const index = (exec.vu.idInTest + exec.vu.iterationInScenario) % PDFS.length;
  const pdf = PDFS[index];

  const params = { tags: { pdf: pdf.name }, timeout: '60s' };
  const response =
    UPLOAD_MODE === 'binary'
      ? http.post(`${BASE_URL}/extract`, pdf.data, {
          ...params,
          headers: { 'Content-Type': 'application/pdf' },
        })
      : http.post(`${BASE_URL}/extract`, { file: http.file(pdf.data, pdf.name, 'application/pdf') }, params);

  check(response, {
    'status 200': (r) => r.status === 200,
    'trae content y page_count': (r) => r.status === 200 && r.json('page_count') > 0 && typeof r.json('content') === 'string',
  });
}

// Al terminar: tabla comparativa contra el profesor + resumen completo en JSON.
export function handleSummary(data) {
  const m = data.metrics;
  const duration = m.http_req_duration.values;
  const ours = {
    requests: m.http_reqs.values.count,
    rate: m.http_reqs.values.rate,
    errorRate: m.http_req_failed.values.rate,
    p50: duration.med,
    p90: duration['p(90)'],
    p95: duration['p(95)'],
    max: duration.max,
  };

  const rows = [
    ['Peticiones procesadas', ours.requests.toFixed(0), PROFESSOR.requests.toFixed(0), ours.requests > PROFESSOR.requests],
    ['Throughput (req/s)', ours.rate.toFixed(2), PROFESSOR.rate.toFixed(2), ours.rate > PROFESSOR.rate],
    ['Tasa de error', pct(ours.errorRate), pct(PROFESSOR.errorRate), ours.errorRate <= PROFESSOR.errorRate],
    ['Latencia p50', secs(ours.p50), secs(PROFESSOR.p50), ours.p50 < PROFESSOR.p50],
    ['Latencia p90', secs(ours.p90), secs(PROFESSOR.p90), ours.p90 < PROFESSOR.p90],
    ['Latencia p95', secs(ours.p95), secs(PROFESSOR.p95), ours.p95 < PROFESSOR.p95],
    ['Latencia máxima', secs(ours.max), secs(PROFESSOR.max), ours.max < PROFESSOR.max],
  ];

  const table = [
    '',
    'Spike k6 (100 VUs) — comparación con el benchmark del profesor',
    '',
    pad('Métrica', 24) + pad('Nuestro', 12) + pad('Profesor', 12) + 'Mejor',
    '-'.repeat(56),
    ...rows.map(([name, value, reference, better]) => pad(name, 24) + pad(value, 12) + pad(reference, 12) + (better ? 'sí' : 'no')),
    '',
    // handleSummary reemplaza el resumen por defecto de k6, que es donde se ven
    // los umbrales: los imprimimos acá para no perder esa información.
    'Umbrales (benchmark del profesor):',
    ...thresholdLines(m),
    '',
    `Checks: ${pct(m.checks.values.rate)} (${m.checks.values.passes} ok, ${m.checks.values.fails} fallidos)`,
    '',
  ].join('\n');

  const stamp = new Date().toISOString().replace(/[:.]/g, '-');
  return {
    stdout: table,
    [`${RESULTS_DIR}/k6-spike-${UPLOAD_MODE}-${stamp}.json`]: JSON.stringify(data, null, 2),
  };
}

function thresholdLines(metrics) {
  return Object.entries(metrics)
    .filter(([, metric]) => metric.thresholds)
    .flatMap(([name, metric]) =>
      Object.entries(metric.thresholds).map(([expression, result]) => `  ${result.ok ? '✓' : '✗'} ${name}: ${expression}`),
    );
}

function pct(value) {
  return `${(value * 100).toFixed(2)} %`;
}

function secs(milliseconds) {
  return `${(milliseconds / 1000).toFixed(2)} s`;
}

function pad(text, width) {
  return String(text).padEnd(width);
}
