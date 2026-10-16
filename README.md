# Deployment Tracker: an end-to-end DevOps platform

A small Flask API that records deployments, wrapped in the full delivery toolchain a production service needs: containerization, CI/CD, infrastructure as code, Kubernetes, and monitoring with alerts.

![CI/CD](https://github.com/mohd-21/devops-platform/actions/workflows/ci-cd.yml/badge.svg)

## Architecture

```
 git push ──► GitHub Actions ──► test ─► validate IaC ─► build image ─► Trivy scan ─► deploy
                                                              │                         │
                                                              ▼                         ▼
                                                        GHCR registry            Kubernetes (2+ pods, HPA)
                                                                                        │ /metrics
                                                                            Prometheus ◄┘──► Grafana
                                                                            (alert rules)
 Terraform ──► AWS: VPC, public/private subnets, ECR repo (scan on push, lifecycle policy)
```

## What's inside

| Path | What it does |
|---|---|
| `app/` | Flask API: `/health`, `/version`, `/api/deployments`, Prometheus `/metrics` |
| `tests/` | pytest suite (7 tests) run on every push and PR |
| `Dockerfile` | Multi-stage build, non-root user, health check |
| `docker-compose.yml` | App + Prometheus + Grafana for local use |
| `.github/workflows/ci-cd.yml` | Test, validate Terraform and K8s manifests, build and push, scan, deploy |
| `k8s/` | Deployment (rolling update, probes, resource limits, read-only root FS), Service, HPA |
| `terraform/` | AWS VPC, subnets across 2 AZs, ECR repository with scanning and lifecycle policy |
| `monitoring/` | Prometheus scrape config, alert rules (error rate, p95 latency, target down), Grafana datasource |

## Run it locally

```bash
docker compose up --build
```

- API: http://localhost:8000/health
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000

Record a deployment and see it in the metrics:

```bash
curl -X POST localhost:8000/api/deployments \
  -H 'Content-Type: application/json' \
  -d '{"service":"checkout","version":"1.4.0","status":"success"}'

curl localhost:8000/api/deployments
curl localhost:8000/metrics | grep deployments_recorded
```

Run the tests without Docker:

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

## Pipeline stages

1. **test:** installs dependencies and runs pytest.
2. **validate-infra:** `terraform fmt -check`, `terraform validate`, and `kubeconform` on the manifests.
3. **build-and-push:** builds the image with a version tag and pushes to GitHub Container Registry (only on `main` and tags).
4. **scan:** Trivy fails the build on fixable CRITICAL/HIGH vulnerabilities.
5. **deploy:** rolls out to Kubernetes and waits for the rollout. It runs only when the repository variable `DEPLOY_ENABLED=true`, so forks do not try to deploy. Setting `SERVICENOW_ENABLED=true` also opens a ServiceNow change request first (see the companion project below).

Secrets for deploy: `KUBE_CONFIG` (base64 kubeconfig), plus `SN_INSTANCE`, `SN_USER` and `SN_PASSWORD` if using ServiceNow.

## Design decisions

- **Multi-stage Docker build and non-root user:** smaller image, smaller attack surface.
- **`maxUnavailable: 0` rolling updates plus readiness probes:** no traffic goes to a pod that is not ready.
- **Immutable ECR tags:** a tag always points to the same image, which makes rollbacks reliable.
- **Alerts on symptoms** (error rate, latency, scrape failure), not on CPU.
- **Deploy gated by a variable and a GitHub Environment:** production deploys can require manual approval.

## Companion project

[servicenow-devops-automation](https://github.com/mohd-21/servicenow-devops-automation) connects this pipeline to ServiceNow: it opens change requests for deployments and auto-triages incidents.

## Notes

The Terraform provisions networking and the registry. It does not create a Kubernetes cluster. Point `KUBE_CONFIG` at any cluster (EKS, kind, minikube).
