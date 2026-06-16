# re-data-service

CSV ingest and dataset metadata API for the Dubai/UAE Real Estate Investment Platform (port **8001**).

## Local dev (without Docker)

```bash
cd re-data-service
pip install -e ".[dev]"
cp .env.example .env
# Edit paths to point at your CSV folder on the host
uvicorn re_data.main:app --host 0.0.0.0 --port 8001 --reload
```

## Docker (standalone smoke)

```powershell
docker build -t re-data-service .
docker run --rm -p 8001:8001 `
  -v "C:\path\to\csv:/data:ro" `
  -e BENCHMARKS_CSV_PATHS="/data/transactions-2026-02-23.csv;/data/Transactions.csv" `
  -e INDEX_CSV_PATH="/data/Residential_Sale_Index.csv" `
  re-data-service
```

Health check (200 when dataset is complete, **503** when `data_state=degraded`):

```powershell
curl -s -w "`nHTTP %{http_code}`n" http://localhost:8001/health
```

## Full stack

From `re-platform/`:

```powershell
docker compose -f docker-compose.yml -f docker-compose.dev.yml --env-file .env.dev up --build
```

Data service docs: http://localhost:8001/docs

## Tests

```bash
pytest
ruff check src tests
mypy src
```
