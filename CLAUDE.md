# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is Airweave?

Airweave is an open-source platform that makes any app searchable for AI agents by syncing data from 50+ sources into vector databases. It serves as a context retrieval layer for RAG systems and AI agents.

## Architecture

Monorepo with four main components:
- **Backend** (`backend/`): Python 3.13, FastAPI, SQLAlchemy async, PostgreSQL
- **Frontend** (`frontend/`): React 18, TypeScript, Vite, ShadCN UI, TailwindCSS
- **Workers**: Temporal for async sync orchestration, Redis for pub/sub
- **MCP Server** (`mcp/`): Node.js, Streamable HTTP transport for AI assistant integration

Data flow: Sources → Entity extraction → Transformation (DAG) → Embedding → Vector DB → Agent queries

## Common Commands

### Local Development (Docker)
```bash
./start.sh                     # Start all services
./start.sh --skip-frontend     # Backend only
./start.sh --restart           # Restart services
./start.sh --destroy           # Tear down everything
```

### Backend
```bash
cd backend
poetry install                 # Install dependencies
poetry run uvicorn airweave.main:app --host 0.0.0.0 --port 8001 --reload  # Dev server

# Tests
poetry run pytest tests/unit                          # Unit tests only
poetry run pytest tests/integration                   # Integration tests
poetry run pytest tests/e2e                           # E2E tests
poetry run pytest tests/unit/test_foo.py              # Single file
poetry run pytest tests/unit/test_foo.py::test_bar    # Single test
poetry run pytest -m "not slow"                       # Skip slow tests

# Code quality
poetry run ruff check .        # Lint
poetry run ruff format .       # Format
poetry run black .             # Alt formatter (88 chars)
poetry run mypy airweave       # Type checking
lint-imports                   # Import architecture validation
```

### Frontend
```bash
cd frontend
npm install                    # Install dependencies
npm run dev                    # Dev server on :8080
npm run build                  # Production build
npm run lint                   # ESLint
```

### MCP Server
```bash
cd mcp
npm install
npm run test:all               # Run all tests
npm run test:mcp               # Core MCP tests
npm run test:http              # HTTP transport tests
npm run test:oauth             # OAuth + org-resolver tests
```

## Backend Structure

```
backend/airweave/
├── api/v1/endpoints/    # FastAPI route handlers (one router per resource)
├── models/              # SQLAlchemy ORM models (UUID PKs)
├── schemas/             # Pydantic request/response schemas
├── crud/                # Database access (base classes: _base_organization, _base_user, _base_public)
├── domains/             # Business logic (service.py, repository.py, protocols.py per domain)
├── platform/
│   ├── sources/         # 50+ source connectors (Notion, Slack, etc.)
│   ├── destinations/    # Vector DB adapters
│   ├── embedding_models/# Embedding providers
│   ├── entities/        # Entity type definitions per source
│   └── temporal/        # Temporal worker and activities
├── core/
│   ├── config/          # Pydantic Settings (env vars)
│   ├── container/       # Dependency injection container + factory
│   ├── exceptions.py    # Custom exception hierarchy
│   └── logging.py       # structlog-based logging
├── adapters/            # External service adapters (PostHog, Stripe, etc.)
└── search/              # Search providers (Vespa)
```

Key concepts:
- `short_name` is a globally unique identifier for sources/entities (e.g., `slack`, `hubspot_crm`)
- `ApiContext` is injected into every endpoint — contains user, org, logger, cache, rate limiter
- Domain services use protocol-based DI; `Container` dataclass holds implementations, `Factory` builds it
- Alembic migrations run automatically on startup (144+ migration files in `backend/alembic/versions/`)

## Frontend Structure

```
frontend/src/
├── components/
│   ├── ui/              # ShadCN base components (40+)
│   └── [feature]/       # Feature-grouped components
├── pages/               # Route-level components
├── lib/
│   ├── api.ts           # API client (token mgmt, org context, SSE, retry)
│   ├── stores/          # Zustand stores (organizations, collections, etc.)
│   ├── auth-context.tsx # Auth0 wrapper with dev-mode fallback
│   └── validation/      # Zod-based validation rules
├── hooks/               # Custom React hooks
├── config/              # env.ts, auth.ts
└── types/index.ts       # Shared TypeScript types (mirrors backend Pydantic schemas)
```

Key patterns:
- API client: always use relative paths, no `/api/v1` prefix — e.g., `apiClient.get('/collections')`
- Auto-injected headers: `X-Organization-ID`, `X-Airweave-Session-ID` (PostHog session replay)
- Zustand for global state, React Query for server state, local state for UI-only concerns
- Component order: hooks → effects → handlers → render
- Path alias: `@/` maps to `./src`

## MCP Server Structure

```
mcp/src/
├── server.ts                    # Core MCP server factory
├── index.ts                     # Local mode entry point (stdio)
├── index-http.ts                # Hosted mode entry point (Streamable HTTP)
├── api/
│   ├── airweave-client.ts       # Airweave API client
│   └── org-resolver.ts          # OAuth org resolution with LRU cache
├── auth/
│   ├── auth0-provider.ts        # OAuth 2.0 provider implementation
│   ├── auth0-callback.ts        # OAuth callback handler
│   ├── oauth-transaction-store.ts # Redis-backed pending auth store
│   ├── registered-clients-store.ts # Dynamic client registration store
│   ├── redis.ts                 # Redis client singleton
│   └── security.ts              # Security utilities (redaction, hashing)
└── types/                       # TypeScript type definitions
```

Deployment modes:
- **Local (stdio)**: Desktop AI clients (Claude Desktop, Cursor, VS Code)
- **Hosted (HTTP)**: Cloud AI platforms (OpenAI Agent Builder, Cursor remote)

Authentication:
- API key via `X-API-Key` header (both modes)
- OAuth 2.0 via `Authorization: Bearer <jwt>` (hosted mode only, when enabled)
- Dual auth middleware resolves API key vs OAuth per request

## API Layer Architecture

### Endpoint Structure
```
api/v1/
├── endpoints/
│   ├── sources.py              # Public API - source metadata
│   ├── source_connections.py   # Public API - connection management
│   ├── collections.py          # Public API - collection CRUD
│   ├── sync.py                 # Internal - sync orchestration
│   ├── organizations.py        # Internal - org management
│   ├── api_keys.py             # Internal - API key management
│   └── connect/                # Connect frontend API - session tokens
├── deps.py                     # Dependency injection & auth resolution
├── auth.py                     # Auth0 integration & token validation
└── middleware.py               # Request processing & CORS
```

### Key Dependencies
- `get_context()`: Returns `ApiContext` with organization, user, logger, analytics
- `require_org_role()`: Enforces admin/owner role checks for mutation endpoints
- `Inject(Protocol)`: Protocol-based DI for domain services

### Authentication Methods
1. **Auth0**: JWT validation (production) or mock (dev with `AUTH_ENABLED=false`)
2. **API Key**: Header `X-API-Key: <key>` for service-to-service
3. **System**: Local dev with `FIRST_SUPERUSER`
4. **Connect Sessions**: Short-lived tokens (10 min TTL) for embedded flows

### Version Convention
- API version is NOT part of URL path — just `host.com/{endpoint}`
- Version information in response headers

## CRUD Layer Architecture

### Base Classes
- `CRUDBaseOrganization`: Organization-scoped resources (most common)
- `CRUDBaseUser`: User-scoped resources (profiles)
- `CRUDPublic`: System-wide resources (sources, destinations)

### BaseContext Pattern
`BaseContext` (parent of `ApiContext` and `SyncContext`) provides:
- `organization`: Always present (required for all operations)
- `user`: Present for user auth, `None` for API keys
- `logger`: Contextual logger (auto-derived from identity)
- `has_feature(flag)`: Check organization feature flags

### Transaction Management
Use `UnitOfWork` for multi-step atomic operations:
```python
async with UnitOfWork(db) as uow:
    obj1 = await crud.create(db, obj_in=data1, ctx=ctx, uow=uow)
    obj2 = await crud.create(db, obj_in=data2, ctx=ctx, uow=uow)
    # Commits on exit, rolls back on exception
```

### Key Invariants
1. Every operation requires `BaseContext` (or subclass)
2. Organization resources are isolated (cross-org access prevented)
3. User tracking is automatic when `track_user=True`
4. Logger is pre-configured via `ctx.logger`

## Sync Architecture

### Core Components
- **SyncFactory**: Builds SyncContext (frozen data), SyncRuntime (live services)
- **SyncOrchestrator**: Coordinates entire sync workflow
- **AsyncSourceStream**: Pull-based streaming with backpressure
- **EntityPipeline**: Action/handler architecture (INSERT/UPDATE/DELETE/KEEP)
- **EntityTracker**: Centralized dedup + progress tracking
- **TokenManager**: OAuth token refresh for long-running syncs

### Concurrency Model
- **Pull-based**: Workers pull entities only when ready (prevents overload)
- **Backpressure**: Bounded queues (default: 10000) naturally throttle producers
- **Worker pool**: Semaphore-controlled concurrency (default: 20 workers)

### Action Handlers
- `DestinationHandler`: Chunking → embedding → vector DB (concurrent)
- `ArfHandler`: Raw entity capture via ArfService (concurrent)
- `PostgresHandler`: Metadata persistence (sequential, last)

###### Progress Tracking
- Event-driven via `EventBus` and `SyncProgressRelay` (EventSubscriber)
- Redis pubsub for real-time updates: `sync_job:{job_id}`
- Snapshot storage: `sync_progress_snapshot:{job_id}` (30 min TTL)

### Orphaned Sync Self-Destruct
Workflows automatically detect orphaned syncs (deleted sync/source_connection) and clean up schedules:
1. Early detection in `create_sync_job_activity`
2. Late detection in `run_sync_activity` via `OrphanedSyncError`
3. Self-destruct via `self_destruct_orphaned_sync_activity` (deletes schedules, logs at INFO level)

## Temporal Module Structure

### Activities (`domains/temporal/activities/`)
Each activity is a `@dataclass` with explicit DI:
- `run_sync.py`: Execute sync job with heartbeating and stall detection
- `create_sync_job.py`: Create sync job record (for scheduled runs)
- `transition_sync_job.py`: Terminal state transitions via SyncJobStateMachine
- `cleanup_stuck_sync_jobs.py`: Detect and cancel stuck jobs
- `self_destruct_orphaned_sync.py`: Clean up schedules for orphaned syncs
- `cleanup_sync_data.py`: Remove Vespa + ARF data for deleted syncs
- `api_key_notifications.py`: Email notifications for expiring API keys

### Workflows (`domains/temporal/workflows/`)
Each workflow is one class per file:
- `run_source_connection.py`: Four-phase orchestration
- `cleanup_stuck_sync_jobs.py`: Periodic stuck-job cleanup
- `cleanup_sync_data.py`: Post-deletion data cleanup
- `api_key_notifications.py`: API key expiration checks

### Worker Wiring (`domains/temporal/worker/`)
`wiring.py` is of DI wiring point — reads dependencies from `container` and instantiates activities.

## ARF (Airweave Raw Format)

Raw entity capture for replay, debugging, and evals.

### Structure
```
raw/{sync_id}/
├── manifest.json          # Sync metadata
├── entities/{id}.json     # One file per entity
└── files/{id}_{name}      # Binary files (optional)
```

### Key Components
- `ArfService` (`domains/arf/service.py`): Write operations during sync
- `ArfReader` (`domains/arf/reader.py`): Entity reconstruction for replay
- `ArfReplaySource` (`domains/arf/replay_source.py`): Internal source for ARF replay
- `StoragePaths` (`domains/storage/paths.py`): Path constants
- Protocols: `ArfServiceProtocol`, `ArfReaderProtocol`
- Storage adapters: Filesystem, Azure Blob, AWS S3, GCP GCS (`adapters/storage/`)

### Integration
`ArfService` is injected into `ArfHandler` via `EntityDispatcherBuilder`. Capture happens during action dispatch (INSERT/UPDATE entities stored, DELETE entities removed).

## Feature Flags

Lightweight organization-level feature flags.

### Backend Usage
```python
from airweave.core.shared_models import FeatureFlag

# Check in endpoints via ApiContext
if not ctx.has_feature(FeatureFlag.S3_DESTINATION):
    raise HTTPException(403, "Feature not available")

# CRUD operations
await crud.organization.enable_feature(db, org_id, FeatureFlag.S3_DESTINATION)
await crud.organization.disable_feature(db, org_id, FeatureFlag.WHITE_LABEL)
flags = await crud.organization.get_org_features(db, org_id)
```

### Frontend Usage
```typescript
import { useOrganizationStore } from '@/lib/stores/organizations';
import { FeatureFlags } from '@/lib/constants/feature-flags';

const hasFeature = useOrganizationStore((state) => state.hasFeature);

{hasFeature(FeatureFlags.S3_DESTINATION) && <S3DestinationCard />}
```

### Adding New Flags
1. Add to `FeatureFlag` enum in `backend/airweave/core/shared_models.py`
2. Add to `FeatureFlags` constants in `frontend/src/lib/constants/feature-flags.ts`
3. Enable for organizations via CRUD or admin panel

## Monke Testing Framework

E2E testing framework for source connectors — creates real test data in external systems, triggers syncs, and verifies results.

### Components
- **Bongos** (`monke/bongos/{short_name}.py`): Test data creation/cleanup via external API
- **Generation schemas** (`monke/generation/schemas/{short_name}.py`): Pydantic schemas for content generation
- **Generation adapters** (`monke/generation/{short_name}.py`): LLM-powered content generation
- **Test configs** (`monke/configs/{short_name}.yaml`): Test flow configuration

### Running Tests
```bash
cd airweave
./monke.sh {short_name}          # Run single connector test
MONKE_VERBOSE=1 ./monke.sh {short_name}  # Verbose logging for debugging
```

### Critical Requirement
Monke tests MUST create and verify ALL entity types that your source connector yields:
1. List all entity types from `generate_entities()` in your source file
2. Create at least one instance of each type in your bongo
3. Return descriptors for all created entities for verification
4. Verify each entity type appears in search index after sync

### Test Flow
1. `cleanup` — Remove leftover test data
2. `create` — Create all entity types
3. `sync` — Trigger Airweave sync
4. `verify` — Search Qdrant for each entity using embedded tokens
5. `update` — Update some entities
6. `sync` — Sync again
7. `verify` — Verify updates appear
8. `partial_delete` — Delete subset of entities
9. `sync` — Sync again
10. `verify_partial_deletion` — Verify deletions (if supported)
11. `complete_delete` — Delete all entities
12. `cleanup` — Final cleanup

## Code Style

### Backend (Python)
- Ruff: 100-char lines, Google docstrings, double quotes
- Async for all I/O operations
- Typed parameters and returns; functions under 50 lines
- RESTful endpoints — version is NOT part of URL path (just `host.com/{endpoint}`)
- Use logger from `ctx` (API) or `sync_context` (during sync)
- Security: never use `random.*` for security values (ruff S311); use `secrets` module

### Frontend (TypeScript)
- TailwindCSS with `cn()` utility for class merging
- Strict typing; shared interfaces in `types/index.ts`
- Never use `Math.random()` (ESLint ban); use `crypto.getRandomValues()` or `crypto.randomUUID()`
- Toast notifications via Sonner: `toast.success()`, `toast.error()`, etc.

## OAuth Browser Flow Contract

1. `POST /source-connections` returns `auth.claim_token` → store in `sessionStorage` as `oauth_claim_token:{source_connection_id}`
2. After OAuth redirect, call `POST /source-connections/{id}/verify-oauth` with `{ claim_token }`
3. Only remove sessionStorage entry after successful `verify-oauth` response

Skipping `verify-oauth` leaves the sync stuck in `PENDING`.

## Infrastructure Notes

- Adjacent `infra-core` repository manages all infrastructure
- Docker Compose for dev; Kubernetes for prod
- PostgreSQL (metadata), Redis (pub/sub + caching), Vespa/Qdrant (vectors), Temporal (orchestration)
- Auth0 for user auth (can disable with `AUTH_ENABLED=False` for local dev)
- Pre-commit hooks enforce ruff, mypy, import-linter, ESLint