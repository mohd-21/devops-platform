"""Deployment Tracker API.

A small Flask service used as the workload for the CI/CD, Kubernetes,
Terraform and monitoring setup in this repository.
"""
import os
import time
from datetime import datetime, timezone

from flask import Flask, jsonify, request, g
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

APP_VERSION = os.getenv("APP_VERSION", "dev")
ENVIRONMENT = os.getenv("APP_ENV", "local")

REQUEST_COUNT = Counter(
    "http_requests_total", "Total HTTP requests", ["method", "endpoint", "status"]
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds", "HTTP request latency", ["endpoint"]
)
DEPLOYMENTS_TOTAL = Gauge("deployments_recorded", "Deployments currently stored")

VALID_STATUSES = {"success", "failed", "rolled_back"}


def create_app() -> Flask:
    app = Flask(__name__)
    store: list[dict] = []

    @app.before_request
    def _start_timer():
        g.start = time.perf_counter()

    @app.after_request
    def _record_metrics(response):
        endpoint = request.url_rule.rule if request.url_rule else "unmatched"
        if endpoint != "/metrics":
            REQUEST_COUNT.labels(request.method, endpoint, response.status_code).inc()
            REQUEST_LATENCY.labels(endpoint).observe(time.perf_counter() - g.start)
        return response

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    @app.get("/version")
    def version():
        return jsonify(version=APP_VERSION, environment=ENVIRONMENT)

    @app.post("/api/deployments")
    def create_deployment():
        body = request.get_json(silent=True) or {}
        missing = [f for f in ("service", "version", "status") if not body.get(f)]
        if missing:
            return jsonify(error=f"missing fields: {', '.join(missing)}"), 400
        if body["status"] not in VALID_STATUSES:
            return (
                jsonify(error=f"status must be one of {sorted(VALID_STATUSES)}"),
                400,
            )
        record = {
            "id": len(store) + 1,
            "service": body["service"],
            "version": body["version"],
            "status": body["status"],
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        store.append(record)
        DEPLOYMENTS_TOTAL.set(len(store))
        return jsonify(record), 201

    @app.get("/api/deployments")
    def list_deployments():
        service = request.args.get("service")
        items = [d for d in store if not service or d["service"] == service]
        return jsonify(items)

    @app.get("/metrics")
    def metrics():
        return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
