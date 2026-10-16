# VIDI SI Platform

Docker stack for a security-awareness platform:

| # | Component | Role | Database |
|---|-----------|------|----------|
| 1 | **GoPhish** | Simulated phishing campaigns + result tracking | SQLite (volume) |
| 2 | **Frappe LMS** | Training platform (modules/plugins, courses) | MariaDB + Redis |
| 3 | **Backstage** | Admin platform | In-memory SQLite (Roadie demo image) |


> Backstage currently uses the [Roadie](https://roadie.io/backstage/docker-image)
> demo image (placeholder, not customizable). The real GoPhish ↔ Frappe
> integration code will later require a custom-built Backstage app.

## Getting started

```bash
cp .env.example .env          # then edit the secrets (a dev .env is already provided)
docker compose up -d          # GoPhish + Frappe + Backstage
```

Create the Frappe site **once** (manual step):

```bash
docker compose run --rm frappe-create-site
docker compose restart frappe-backend frappe-frontend
```

Access:

- GoPhish admin  → http://localhost:3333
- GoPhish phish  → http://localhost:8080
- Frappe LMS     → http://localhost:8000  (host `lms.localhost`)
- Backstage      → http://localhost:7007


## Magic login links (`vidi_integration` app)

Custom Frappe app (`./frappe-apps/vidi_integration`) that generates auto-login
links to an LMS course: click → the user is authenticated → redirected to the
course. Token is **hashed** (SHA-256) in the database, with a **TTL** (7 days by
default), **reusable** until expiry, and revocable.An external system
calls the API and sends the email itself.

**Build + install (once)** — overlay on top of `vidi-lms:latest`:

```bash
./build-lms-image.sh          # 1. base (if not already built)
./build-app-image.sh          # 2. overlay + vidi_integration -> vidi-lms:latest
docker compose up -d
docker compose run --rm frappe-install-app     # adds to apps.txt + installs on the site
docker compose restart frappe-backend frappe-scheduler frappe-queue frappe-websocket
```

**Generate a link** (from the CLI, or via the REST API for Backstage):

**API access (Backstage / external).** The `create_magic_link` endpoint is
protected. To call it, use an **API-only service user** (only the `Magic Link Manager` role, no desk access). Create it and
retrieve its key/secret (once):

```bash
docker compose run --rm frappe-create-service-user
# -> { "user": "svc-magic-link@vidi.local", "api_key": "...", "api_secret": "..." }
# (re-running rotates the secret)
```

Then call over HTTP:

```bash
curl -X POST http://localhost:8000/api/method/vidi_integration.api.create_magic_link \
  -H "Authorization: token <api_key>:<api_secret>" \
  -H "Content-Type: application/json" \
  -d '{"user":"learner@vidi.local","course":"<course-name>","ttl_days":7}'
```

Open `magic_url` in a private window → you land **logged in** on the course.


## Create a user

```bash
docker compose exec frappe-backend \
  bench --site lms.localhost add-system-manager admin@vidi.local \
    --first-name Admin --password 'VidiAdmin123!'
```


## Things to know

**GoPhish** — SQLite database (`config/gophish/config.json` → `db_name: sqlite3`),
persisted in the `gophish-data` volume (file `/opt/gophish/data/gophish.db`).

**Frappe** — `FRAPPE_IMAGE` must point to an image that contains the `lms` app.
If `frappe/lms:latest` doesn't work, build an image with
[frappe_docker](https://github.com/frappe/frappe_docker) via `apps.json` and your
own plugins/courses, then update `.env`.

**Frappe LMS** — the published `ghcr.io/frappe/lms:*` images (tested `stable` and
`v2.65.0`) only contain the `frappe` app, not `lms` (`ls apps` → `frappe` only).
So you must **build a custom image** with the app baked in:

```bash
./build-lms-image.sh                         # -> local image vidi-lms:latest
# verify:
docker run --rm --entrypoint bash vidi-lms:latest -lc 'ls -1 apps; python -c "import lms"'
# then in .env:  FRAPPE_IMAGE=vidi-lms:latest
docker compose up -d
docker compose run --rm frappe-create-site
```

The script clones [frappe_docker](https://github.com/frappe/frappe_docker) and
builds via `apps.json` (passed as a BuildKit secret), the official method
described here:
[docs/02-setup/02-build-setup.md](https://github.com/frappe/frappe_docker/blob/main/docs/02-setup/02-build-setup.md).
This is also where you add your own plugins/courses (add their repos to the
`apps.json` in `build-lms-image.sh`).

**Backstage** — [Roadie](https://roadie.io/backstage/docker-image) demo image
(`roadiehq/community-backstage-image`), ready to use and started by default.
Optional: set `BACKSTAGE_GITHUB_TOKEN` in `.env` (a PAT with scopes
`repo,user,read:org,read:discussion`) to populate the GitHub catalog.

