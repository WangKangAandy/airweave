# AGENTS.md - Airweave Agent Guidelines

## Build, Lint, and Test Commands

### Backend (Python 3.13, FastAPI, SQLAlchemy async)

```bash
cd backend

# Install dependencies
poetry install

# Development server
poetry run uvicorn airweave.main:app --host 0.0.0.0 --port 8001 --reload

# Tests
poetry run pytest tests/unit                          # Unit tests only
poetry run pytest tests/integration                   # Integration tests
poetry run pytest tests/e2e                           # E2E tests
poetry run pytest tests/unit/test_foo.py             # Single file
poetry run pytest tests/unit/test_foo.py::test_bar   # Single test
poetry run pytest -m "not slow"                      # Skip slow tests

# Code quality
poetry run ruff check .        # Lint
poetry run ruff format .       # Format
poetry run black .             # Alt formatter (88 chars)
poetry run mypy airweave       # Type checking
lint-imports                   # Import architecture validation
```

### Frontend (React 18, TypeScript, Vite, ShadCN UI)

```bash
cd frontend

# Install dependencies
npm install

# Development
npm run dev                    # Dev server on :8080

# Build
npm run build                  # Production build
npm run build:dev             # Dev build

# Tests
npm run test                   # Run tests
npm run test:watch             # Watch mode

# Code quality
npm run lint                   # ESLint
```

## Code Style Guidelines

### Backend (Python)

**Formatting**
- Line length: 100 chars (ruff), 88 chars (black), 100 chars (isort)
- Quote style: double quotes
- Docstring convention: Google style with args/returns type annotations

**Imports**
- Order: stdlib → third-party → local application
- Use isort via ruff (automatically handled)
- Avoid top-level imports in modules unless necessary

**Types**
- Python 3.13+, async for all I/O operations
- Typed parameters and returns required
- Keep functions under 50 lines
- SQLAlchemy models use UUID primary keys

**Naming**
- `short_name` is globally unique identifier (e.g., `slack`, `hubspot_crm`)
- Descriptive names over comments

**Error Handling**
- Custom exception hierarchy in `core/exceptions.py`
- Error responses via custom exceptions
- Never use `random.*` for security values - use `secrets` module instead

**Project Structure**
```
backend/airweave/
├── api/v1/endpoints/    # FastAPI route handlers (one router per resource)
├── models/              # SQLAlchemy ORM models
├── schemas/             # Pydantic request/response schemas
├── crud/                # Database access
├── domains/             # Business logic (service.py, repository.py, protocols.py)
├── platform/
│   ├── sources/         # Source connectors
│   ├── destinations/   # Vector DB adapters
│   ├── entities/       # Entity type definitions
│   └── temporal/       # Temporal sync orchestration
└── core/               # Config, logging, exceptions
```

**Logging**
- Use logger from `ctx` (API) or `sync_context` (during sync)
- Stick to log level standards

**API Convention**
- RESTful endpoints - version is NOT in URL path
- Consistent response structures
- Logger injected via `ctx` dependency

### Frontend (TypeScript)

**Formatting & Style**
- TailwindCSS with `cn()` utility for class merging
- Strict typing - avoid `any` types
- Use interfaces from `@/types/index.ts`
- Use shared interfaces in `types/index.ts` (mirrors backend Pydantic schemas)

**Component Order**
1. Hooks first
2. Effects next
3. Handlers
4. Render

**State Management**
- Zustand for global state
- React Query for server state
- Local state for UI-only concerns

**API Integration**
- Always use relative paths (no `/api/v1` prefix)
- Check `response.ok` before parsing
- Auto-injected headers: `X-Organization-ID`, `X-Airweave-Session-ID`

**Security**
- Never use `Math.random()` - use `crypto.getRandomValues()` or `crypto.randomUUID()`
- Never use `innerHTML` or `dangerouslySetInnerHTML` (XSS prevention)
- Use `safeRedirectPath()` from `lib/utils/url-validation.ts` for redirects

**Error Handling**
- Toast notifications via Sonner: `toast.success()`, `toast.error()`, etc.
- Use appropriate toast types (success, error, info, warning)

**OAuth Browser Flow**
1. `POST /source-connections` returns `auth.claim_token` → store in `sessionStorage` as `oauth_claim_token:{source_connection_id}`
2. After OAuth redirect, call `POST /source-connections/{id}/verify-oauth` with `{ claim_token }`
3. Only remove sessionStorage entry after successful `verify-oauth` response

### Testing

**Backend Test Markers**
- `@pytest.mark.unit` - fast, isolated
- `@pytest.mark.integration` - requires database/services
- `@pytest.mark.live_integration` - requires live cloud infrastructure
- `@pytest.mark.e2e` - end-to-end
- `@pytest.mark.slow` - long-running

Async mode is `auto` - async test functions detected automatically.

### Monke (E2E Framework)

Located in `monke/`. Tests source connectors end-to-end:
- `monke/bongos/{short_name}.py` - test data creation/cleanup
- `monke/generation/schemas/{short_name}.py` - generation schemas
- `monke/configs/{short_name}.yaml` - test configuration

### PostHog Analytics

- Import from `airweave.analytics.service`
- All events automatically include `environment` property
- Use `time.monotonic()` for duration measurements (not `time.time()`)
- Frontend sends PostHog session ID via `X-Airweave-Session-ID` header

### Architecture Notes

- Monorepo with Backend, Frontend, Workers (Temporal/Redis), MCP Server
- Data flow: Sources → Entity extraction → Transformation (DAG) → Embedding → Vector DB
- `ApiContext` injected into every endpoint - contains user, org, logger, cache, rate limiter
- Domain services use protocol-based DI
- Alembic migrations run automatically on startup

## Local Development

### Starting the Stack

Use `start.sh` to run the full local development environment:

```bash
./start.sh                        # Interactive setup
./start.sh --noninteractive       # CI/automated setup
./start.sh --skip-frontend       # Backend only
./start.sh --restart              # Restart existing containers
./start.sh --recreate             # Fresh containers, keep volumes
./start.sh --destroy              # Complete cleanup

# With environment variables
SKIP_FRONTEND=1 ./start.sh
NONINTERACTIVE=1 ./start.sh
```

### Service URLs (when running locally)

| Service       | URL                     |
|---------------|------------------------|
| Backend API   | http://localhost:8001  |
| Frontend UI   | http://localhost:8080  |
| Connect Widget| http://localhost:8082 |
| Temporal UI   | http://localhost:8088  |
| Vespa         | http://localhost:8081  |
| PostgreSQL    | localhost:5432         |

### Troubleshooting

```bash
# View logs
docker logs airweave-backend
docker logs airweave-frontend

# Stop services
docker compose -f docker/docker-compose.yml down
```

Frontend change not taking effect after code edits:
- See `docs/debug/frontend-change-not-effective.md` for the quick rebuild/restart workflow and `frontend/dist` permission fix.
