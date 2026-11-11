# CASS — Conversational AI SQL System

Ask questions about a PostgreSQL database using a local Ollama model, inspect the SQL, and view the results. The browser supports authenticated streaming and direct SQL queries.

![Query dashboard](docs/screenshots/release-query.png)

## Local setup

Python 3.12, Node 24, PostgreSQL and Ollama are required.

```bash
git clone https://github.com/xt67/CASS.git
cd CASS
ollama pull qwen3:4b
docker compose up -d postgres
```

Initialize a dedicated read-only role using `database/restricted-role.sql` as the database owner, then set its password separately. The sample schema and seed data are loaded by Compose on first startup.

From `backend/`:

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements-test.lock
uvicorn cass.server.app:app --app-dir src --host 127.0.0.1 --port 8001
```

Set process environment variables before launching:

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | Connection URL for the restricted role |
| `OLLAMA_MODEL` | Use `qwen3:4b` for the locally validated configuration; fallback default `sqlcoder:7b` requires separate installation/validation |
| `OLLAMA_BASE_URL` | Defaults to `http://localhost:11434` |
| `CASS_API_KEY` | A strong server-side token; enter it via the database connection button in the browser |
| `CASS_ALLOW_ANONYMOUS` | Set to `1` only for explicit local development without a token |
| `CASS_ALLOWED_ORIGINS` | Comma-separated frontend origins; defaults to `http://localhost:3000` |
| `CASS_MAX_ROWS` | Maximum query result size, default 500 |
| `CASS_QUERY_TIMEOUT` | Query timeout in seconds, default 10 |

The backend reads process environment variables; a `.env` file is not automatically loaded. Data routes fail closed when authentication is unconfigured. Keep deployment behind HTTPS and use a restricted database role. Tokens stay in browser memory, never in query URLs or frontend build variables.

From `frontend/`:

```bash
npm ci
npm run dev
```

Open `http://localhost:3000`. For a separate production backend, set `VITE_API_BASE_URL` to its HTTPS origin before `npm run build`; otherwise configure a same-origin `/api` reverse proxy. No API key belongs in a `VITE_` variable.

## Validation and limits

```bash
# repository root
python -m pytest backend/tests -q
# frontend directory
npm test
npm run lint
npm run build
```

Optional live PostgreSQL tests require `CASS_TEST_DATABASE_URL` pointing to a disposable database. They create and remove uniquely named test roles/tables. The CI service uses trust authentication only inside its disposable test environment; production must use password authentication.

Generated and direct SQL pass through single-query AST validation, a read-only transaction, a row cap and a timeout. Parameter values are bound and table identifiers quoted. These controls are not a complete sandbox: the role must only access data intended for users, and deployment still needs concurrency/rate limits appropriate to its audience.

Locally verified on 11 November 2026: restricted-role write denial, row limits, timeout recovery, authentication, streaming success/failure, browser query execution, production build, and three reference questions using `qwen3:4b`. See `docs/local-model-validation.json`. This small sample does not establish general SQL accuracy. `backend/validate_local_model.py` reruns it against a seeded disposable database. No hosted deployment has been performed.

## Attribution and repository history

The earlier README credited the **Cat Communist Party** project and linked to `Cat-Communist-Party-CCP/CASS`; that credit is retained here. The inspected commits identify **Rayan Rahman** and describe the UI as **Chartbrew-style**. This review does not establish ownership of third-party assets or change their attribution.

The previous README advertised MIT, but this checkout contains no LICENSE file. No license has been invented or granted by this update; confirm the intended license before redistribution. Broken links to nonexistent API, architecture and contribution documents have been replaced with the working instructions above.
