# Production deployment

TrialSync is an academic pre-screening demonstration using synthetic data only.
This deployment stack places Nginx, the API, and PostgreSQL on a private Docker
network. Only Nginx is published to the host at `127.0.0.1:8081`; PostgreSQL
has no host port. Configure Cloudflare Tunnel with origin
`http://127.0.0.1:8081` and public hostname `trialsync.atuls.me`.

## First deployment

Install Docker Engine with the Compose plugin and Cloudflare Tunnel on the host.
From the repository root, create the production environment file:

```bash
cp .env.production.example .env.production
chmod 600 .env.production
```

Generate a database password and authentication secret:

```bash
openssl rand -hex 32
openssl rand -hex 48
```

Put the first value in `POSTGRES_PASSWORD`. Put a URL-encoded version of that
same value in `DATABASE_URL` after `trialsync:` (hex output needs no encoding).
Put the second value in `TRIALSYNC_AUTH_SECRET`. Do not commit
`.env.production`. Optionally set `GROQ_API_KEY` on the host; leaving it empty
keeps the deterministic/canonical fallbacks available.

Start the complete stack. The `migrate` service runs `alembic upgrade head`
after PostgreSQL is healthy, and the API is not started until it succeeds.

```bash
docker compose --env-file .env.production -f compose.prod.yaml up -d --build --wait
```

Configure the tunnel (for example in `~/.cloudflared/config.yml`) with this
origin, then restart the tunnel service according to its installation method:

```yaml
ingress:
  - hostname: trialsync.atuls.me
    service: http://127.0.0.1:8081
  - service: http_status:404
```

## Operations

Check the application locally and through the public URL:

```bash
curl --fail http://127.0.0.1:8081/health/ready
curl --fail https://trialsync.atuls.me/health/ready
docker compose --env-file .env.production -f compose.prod.yaml ps
```

Inspect service logs:

```bash
docker compose --env-file .env.production -f compose.prod.yaml logs --follow frontend backend migrate db
```

To upgrade from Git, review the changes, rebuild images, and rerun the same
health-gated deployment command. The migration job is idempotent when already
at the Alembic head revision.

```bash
git pull --ff-only
docker compose --env-file .env.production -f compose.prod.yaml up -d --build --wait
```

## Database backup and restore

Create a compressed logical PostgreSQL backup before upgrades and keep it away
from the repository:

```bash
mkdir -p backups
docker compose --env-file .env.production -f compose.prod.yaml exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > backups/trialsync-$(date +%F-%H%M%S).dump
```

Restoring replaces database contents. Stop the application first, retain the
old backup until the restored stack passes health checks, then restore a known
good dump:

```bash
docker compose --env-file .env.production -f compose.prod.yaml stop frontend backend
cat backups/trialsync-YYYY-MM-DD-HHMMSS.dump | docker compose --env-file .env.production -f compose.prod.yaml exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner'
docker compose --env-file .env.production -f compose.prod.yaml up -d --wait backend frontend
curl --fail http://127.0.0.1:8081/health/ready
```

For a restore from an older application version, first check out the matching
Git revision and run its migration set before bringing the newer version back.
Do not manually change the schema during application startup.

## Safe stop

Stop containers without deleting the persistent database volume:

```bash
docker compose --env-file .env.production -f compose.prod.yaml down
```

Do not add `--volumes` unless intentionally destroying the database after a
verified backup.
