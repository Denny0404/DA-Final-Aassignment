  # Group 8 - DA-Final-Aassignment — Automated MySQL + Flyway + CI/CD + Observability (SigNoz)
This repo contains a reproducible MySQL environment, automated schema management with **Flyway**, a **GitHub Actions** pipeline (runnable locally via `act`), and **OpenTelemetry** instrumentation that streams logs/traces/metrics to **SigNoz** (via the `docker-infra` submodule).

> Works in **GitHub Codespaces** or any Linux dev host with Docker.

---
## Quick Start (TL;DR)

```bash
# 0) Clone
git clone https://github.com/Denny0404/DA-Final-Aassignment.git
cd DA-Final-Aassignment

# 1) Add SigNoz infra (only first time)
git submodule add https://github.com/rhildred/docker-infra docker-infra
git submodule update --init --recursive
cd docker-infra
# If this repo contains patch.diff, apply it once (harmless if not present)
[ -f patch.diff ] && patch signoz/deploy/docker/docker-compose.yaml < patch.diff || true
cd ..

# 2) Create local secrets for MySQL (NOT committed)
cat > .secrets <<'EOF'
DB_HOST=127.0.0.1
DB_ADMIN_USER=root
DB_PASSWORD=Secret5555
DB_NAME=project_db
EOF

# 3) Start MySQL + tools via Ansible
ansible-playbook up.yml

# 4) Initialize DB (schema + flyway)
mysql -h 127.0.0.1 -u root -pSecret5555 -e "CREATE DATABASE IF NOT EXISTS project_db;"
docker run --rm --network host -v "$PWD/migrations:/flyway/sql" redgate/flyway \
  -user=root -password=Secret5555 \
  -url="jdbc:mysql://127.0.0.1:3306/project_db?allowPublicKeyRetrieval=true&useSSL=false" \
  migrate

# 5) Run the CI locally (nektos/act). If docker says 'port already allocated', see Troubleshooting.
bin/act

# 6) Start SigNoz (observability)
cd docker-infra
docker compose up -d
cd ..

# 7) Send telemetry by running the instrumented workload
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
export OTEL_EXPORTER_OTLP_PROTOCOL=http/proto
export OTEL_EXPORTER_OTLP_INSECURE=true
export OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED=true
opentelemetry-instrument --logs_exporter otlp --metrics_exporter otlp \
  --traces_exporter otlp --service_name climate-test \
  python3 scripts/multi_thread_queries.py
```

Then open **SigNoz UI** (Codespaces: Ports panel → open the public URL for `3301` or your forwarded port). Verify:
- **Services** → `climate-test` is listed
- **Traces** → spans named `INSERT`, `SELECT`, `UPDATE`
- **Logs** → collector + app logs visible

---
## Repository Layout

```
.
├── .github/workflows/ci_cd_pipeline.yml   # CI/CD – MySQL, Flyway, concurrent test, validation
├── migrations/                            # Flyway SQL migrations (V1__*, V2__*...)
├── scripts/
│   └── multi_thread_queries.py            # Concurrent workload with OTEL export
├── schema_changes.sql                     # bootstrap schema for CI
├── up.yml / down.yml                      # Ansible for local MySQL lifecycle + act setup
├── docker-infra/                          # SigNoz + OTel Collector (git submodule)
└── .secrets                               # local-only env (ignored by git)
```

> Ensure `.secrets` is listed in `.gitignore`. Never commit it.

---
## Prerequisites

- Docker + Docker Compose
- Python 3.10+ (Codespaces already has Python 3.12)
- MySQL client
- `ansible` (Codespaces has it pre-installed via devcontainer)
- `nektos/act` (installed by `up.yml`), or install manually
- Python libs:
  ```bash
  pip3 install -U opentelemetry-api opentelemetry-sdk \
    opentelemetry-exporter-otlp opentelemetry-instrumentation \
    opentelemetry-instrumentation-mysql opentelemetry-instrumentation-threading \
    mysql-connector-python
  ```

---
## 1) Submodule & Local Infra

```bash
git submodule add https://github.com/rhildred/docker-infra docker-infra
git submodule update --init --recursive
cd docker-infra
[ -f patch.diff ] && patch signoz/deploy/docker/docker-compose.yaml < patch.diff || true
cd ..
```

The submodule brings SigNoz (UI + ClickHouse) and the OTel Collectors.

---
## 2) Local MySQL Lifecycle (Ansible)

```bash
# Start
ansible-playbook up.yml

# Stop / clean
ansible-playbook down.yml
```

`up.yml` also installs MySQL client, Python connectors, and `act`.

### Connect to DB

```bash
mysql -h 127.0.0.1 -u root -pSecret5555
```

---
## 3) Database Initialization

### 3.1 Create database (idempotent)
```bash
mysql -h 127.0.0.1 -u root -pSecret5555 -e "CREATE DATABASE IF NOT EXISTS project_db;"
```

### 3.2 Run Flyway migrations
```bash
docker run --rm --network host -v "$PWD/migrations:/flyway/sql" redgate/flyway \
  -user=root -password=Secret5555 \
  -url="jdbc:mysql://127.0.0.1:3306/project_db?allowPublicKeyRetrieval=true&useSSL=false" \
  migrate
```

**Verify Flyway applied all versions:**
```bash
mysql -h 127.0.0.1 -u root -pSecret5555 -D project_db \
  -e "SELECT installed_rank, version, description, success FROM flyway_schema_history ORDER BY installed_rank;"
```

**Verify table & columns (humidity present):**
```bash
mysql -h 127.0.0.1 -u root -pSecret5555 -D project_db -e "DESCRIBE ClimateData;"
```

---
## 4) CI/CD Locally with `act`

The workflow **`.github/workflows/ci_cd_pipeline.yml`**:
- starts an ephemeral MySQL container
- applies `schema_changes.sql`
- runs **Flyway** against `migrations/`
- executes **concurrent workload** (`scripts/multi_thread_queries.py`)
- validates schema + row counts

**Run it locally:**
```bash
# If you previously used a container literally named "mysql", clean it up first
docker rm -f mysql || true

# Run the workflow
bin/act
# If you're in Codespaces and see runner image issues, try:
# bin/act -P ubuntu-latest=-self-hosted
```

**Common act errors:**
- *“container name ‘/mysql’ is already in use”* → `docker rm -f mysql`
- *“Bind for :::3306 failed: port is already allocated”* → stop any host MySQL or change ports in the workflow (or ensure the container was removed).

---
## 5) Observability (SigNoz)

### 5.1 Start SigNoz
```bash
cd docker-infra
docker compose up -d
cd ..

# Check collector is healthy
docker logs signoz-otel-collector | egrep "Starting .*server|Everything is ready|Health Check state change|collector.*running" || true
```

**UI access**
- Default SigNoz UI is on **port 3301**. In Codespaces, open the **Ports** panel and make the port public, then click its URL. (Your URL may look like `https://<id>-3301.app.github.dev/`.)

### 5.2 Export OTEL data from the app

Use **HTTP/proto** to the collector (simplest in Codespaces):
```bash
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
export OTEL_EXPORTER_OTLP_PROTOCOL=http/proto
export OTEL_EXPORTER_OTLP_INSECURE=true
export OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED=true

opentelemetry-instrument --logs_exporter otlp --metrics_exporter otlp \
  --traces_exporter otlp --service_name climate-test \
  python3 scripts/multi_thread_queries.py
```

(Alternative gRPC config):
```bash
export OTEL_EXPORTER_OTLP_ENDPOINT=localhost:4317
export OTEL_EXPORTER_OTLP_INSECURE=true
opentelemetry-instrument --logs_exporter otlp --metrics_exporter otlp \
  --traces_exporter otlp --service_name climate-test \
  python3 scripts/multi_thread_queries.py
```

> If you see “Attempting to instrument while already instrumented”, it’s safe. It means both your script and the wrapper are instrumenting. You can remove explicit instrumentor calls from your script if you prefer using only `opentelemetry-instrument`.

### 5.3 Verify in SigNoz

- **Services** → you should see `climate-test` with latency/ops.
- **Traces** → search for spans named `INSERT`, `SELECT`, `UPDATE`.
- **Logs** → app logs and collector logs appear in Logs Explorer.

### 5.4 (Optional) Dashboard & Alerts

- **Dashboard**: create panels for **CPU**, **p95 latency** per operation, and **error logs**.
- **Alerts**: 
  - High CPU (>80% for 5m) → Email action
  - Long query (p95 > 200ms for 5m) for `climate-test` → Email action
- Configure **Email notification channel** under Settings → Notification Channels.

---
## 6) Run the Concurrent Test Manually

```bash
# Uses mysql-connector-python and threading to generate load
python3 scripts/multi_thread_queries.py
```

You should see console lines like `Records with temperature > 20°C: N`. In SigNoz, new traces/logs will show immediately (refresh the last 15–30 minutes window).

---
## 7) Verification Commands (one-liners)

```bash
# Schema & columns
mysql -h 127.0.0.1 -u root -pSecret5555 -D project_db -e "DESCRIBE ClimateData;"

# Row counts and temp>20
mysql -h 127.0.0.1 -u root -pSecret5555 -D project_db \
  -e "SELECT COUNT(*) total, SUM(temperature > 20) over20 FROM ClimateData;"

# Flyway history
mysql -h 127.0.0.1 -u root -pSecret5555 -D project_db \
  -e "SELECT installed_rank, version, description, success FROM flyway_schema_history ORDER BY installed_rank;"

# Collector ports
ss -lntp | egrep '4317|4318' || true

# OTLP HTTP endpoints (POST-only, a GET/HEAD returns 405 which is OK)
curl -I http://localhost:4318/v1/traces
curl -I http://localhost:4318/v1/metrics
```

---
## 8) Troubleshooting

- **RSA public key not available** (Flyway → MySQL 8/9): add `?allowPublicKeyRetrieval=true&useSSL=false` to JDBC URL and run with `--network host`.
- **act says Unknown Properties / schema validation**: your YAML must have `on:`, `jobs:`, `runs-on:`, `steps:` with correct indentation. Don’t use `|| 'default'` in expressions—GitHub Actions allows it, but `act`’s schema may not.
- **Port 3306 already allocated**: stop/remove existing MySQL containers or change the port mapping in the workflow. `docker ps -a` then `docker rm -f <id>`.
- **Attempting to instrument while already instrumented**: remove duplicate explicit instrumentors from code if using `opentelemetry-instrument` wrapper.

---
## 9) Clean Up

```bash
# Stop SigNoz
cd docker-infra && docker compose down -v && cd ..

# Stop local MySQL & tools
ansible-playbook down.yml

# Remove lingering containers (optional)
docker rm -f mysql || true
```

---
## 10) What to include in your submission

- **SQL folder** (`migrations/`), **scripts**, and the **workflow** file
- **Screenshots**: Logs, Traces, Services, Dashboard, Alerts
- Short **Performance analysis** (before/after, any index changes)
- This **README.md**

---
## Credits

- Flyway by Redgate
- SigNoz (open-source APM)
- OpenTelemetry (logs/traces/metrics)
