"""Tests del script que compara nuestros resultados con los del profesor.

Los datos de entrada imitan la estructura real de los archivos de k6
(handleSummary) y de Vegeta (report -type=json y encode --to csv).
"""

import math

from compare_results import k6_metrics, median, read_vegeta_csv, render, vegeta_metrics

K6_SUMMARY = {
    "metrics": {
        "http_reqs": {"values": {"count": 1500, "rate": 37.5}},
        "http_req_failed": {"values": {"rate": 0.0}},
        "http_req_duration": {"values": {"med": 1200.0, "p(90)": 4000.0, "p(95)": 9000.0, "max": 12000.0}},
    }
}

VEGETA_REPORT = {
    "throughput": 24.5,
    "success": 0.9,
    "status_codes": {"200": 1350, "503": 120, "0": 30},
    "latencies": {"50th": 8_000_000_000},
}


def by_name(metrics):
    return {metric.name: metric for metric in metrics}


def test_k6_metrics_are_converted_to_the_professor_units():
    metrics = by_name(k6_metrics(K6_SUMMARY))

    assert metrics["Throughput sostenido"].ours == 37.5
    assert metrics["Latencia p50"].ours == 1.2  # ms → s
    assert metrics["Tasa de error"].ours == 0.0


def test_k6_comparison_marks_each_metric_independently():
    metrics = by_name(k6_metrics(K6_SUMMARY))

    assert metrics["Latencia p90"].better  # 4.00 s < 7.83 s
    assert not metrics["Latencia p95"].better  # 9.00 s > 8.80 s
    assert metrics["Tasa de error"].better  # 0 % igual a 0 % cuenta como cumplido


def test_vegeta_counts_successes_and_client_timeouts_from_status_codes():
    metrics = by_name(vegeta_metrics(VEGETA_REPORT, requests=[]))

    assert metrics["Peticiones exitosas"].ours == 1350
    assert metrics["Timeouts de cliente (código 0)"].ours == 30
    assert metrics["Tasa de éxito"].ours == 90.0


def test_vegeta_success_only_median_ignores_rejected_requests():
    requests = [(200, 4_000_000_000), (200, 6_000_000_000), (503, 1_000_000), (0, 30_000_000_000)]

    metrics = by_name(vegeta_metrics(VEGETA_REPORT, requests))

    assert metrics["Latencia p50 (solo exitosas)"].ours == 5.0


def test_median_of_even_and_odd_lists_and_empty():
    assert median([3, 1, 2]) == 2
    assert median([4, 1, 2, 3]) == 2.5
    assert math.isnan(median([]))


def test_reads_code_and_latency_from_vegeta_csv(tmp_path):
    csv_file = tmp_path / "vegeta.csv"
    csv_file.write_text(
        "1700000000000000000,200,1500000000,9000,800,,,,0,POST,http://proxy:8080/extract,\n"
        "1700000000020000000,0,30000000000,9000,0,Post timeout,,,1,POST,http://proxy:8080/extract,\n",
        encoding="utf-8",
    )

    assert read_vegeta_csv(csv_file) == [(200, 1_500_000_000), (0, 30_000_000_000)]


def test_markdown_table_has_one_row_per_metric():
    table = render("Spike", k6_metrics(K6_SUMMARY), markdown=True)

    assert table.count("\n| ") == 1 + len(k6_metrics(K6_SUMMARY))  # encabezado + filas
