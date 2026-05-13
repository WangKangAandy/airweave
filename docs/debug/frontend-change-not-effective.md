# Frontend change not effective (local Docker)

Use this when frontend code changed but UI still shows old behavior.

## Why this happens

- Local `airweave-frontend` serves static files from `frontend/dist` via `serve`, not `vite dev`.
- If `frontend/dist` is stale, container restart alone still serves old assets.
- In some flows, `frontend/dist` files are owned by `root`, so local `npm run build` fails with `EACCES`.

## Fast verification path

1) Rebuild frontend assets locally:

```bash
cd frontend
npm run build
```

2) Restart only frontend container:

```bash
docker restart airweave-frontend
```

3) Hard refresh browser (`Ctrl+Shift+R`).

## If build fails with EACCES on `frontend/dist`

Fix ownership, then rebuild:

```bash
docker exec -u 0 airweave-frontend sh -c 'chown -R $(id -u):$(id -g) /app/dist'
cd frontend
npm run build
docker restart airweave-frontend
```

## Notes

- Full `./start.sh --restart` is not required to validate frontend-only code changes.
- `./start.sh --restart` now includes auto-repair logic for `frontend/dist` permissions.
