# PriceBuddy

Self-hosted price comparison tracker — [docs](https://pricebuddy.jez.me/).

| | |
|---|---|
| URL | https://price.lab.marioverde.com.br |
| Images | `jez500/pricebuddy:v1.0.57`, `jez500/seleniumbase-scrapper:v1.0.1` |
| Database | lab PostgreSQL, CT 103 (`10.0.0.2`), database + role `pricebuddy` |
| Volume | `pricebuddy_storage` → `/app/storage` (sessions, logs, cache) |
| Network | `pricebuddy_network` (bridge), no published ports |

## Services

* `app` — Laravel 11 + Filament behind Apache on container port 80. On boot it waits for
  `DB_HOST:DB_PORT`, runs `php artisan buddy:init-db` (migrates, seeds stores, seeds the first
  admin on an empty database), caches config, then starts supervisord (apache + `schedule:run`
  cron + `queue:work`).
* `scraper` — Selenium/Playwright scraper API on port 3000. The app talks to it via
  `SCRAPER_BASE_URL=http://scraper:3000`. All page fetching happens here, not in `app`.

## Database

External: the shared lab PostgreSQL on CT 103. The stack does not run a database container.

Provision once (see the deploy plan), then set `DB_*` in the Komodo stack Environment:

```sql
CREATE ROLE pricebuddy LOGIN PASSWORD '…';
CREATE DATABASE pricebuddy OWNER pricebuddy ENCODING 'UTF8';
```

`buddy:init-db` runs `migrate:fresh` on an empty database and plain `migrate --force` afterwards,
so the schema is owned entirely by the app.

## Deploy

Komodo stack `pricebuddy` → repo `homelab`, branch `master`, run directory
`docker/personal/pricebuddy`, env file `.env` (written by Komodo from the stack Environment).

## Day-2 operations

```bash
# refresh every tracked product now (normally the 06:00 cron does this)
docker compose exec app php artisan buddy:fetch-all

# rebuild URL match keys after changing URL_MATCHING_* env vars
docker compose exec app php artisan urls:renormalize

# tail the Laravel log
docker compose exec app tail -n 50 storage/logs/laravel.log
```

## Bumping the app

Edit the image tags in `compose.yaml`, commit, merge to `master`, then `PullStack` + `DeployStack`
in Komodo. Pinned tags only — never `:latest`; the app runs migrations on boot.

## Notes

* Seeded store list covers Australia and the USA only (upstream seed data). Brazilian stores
  (Amazon BR, Mercado Livre, KaBuM…) are added by hand in the UI, with locale `pt_BR` and currency `BRL`.
* Not WAN-exposed: `.lab` hostname only, no `homelab.wan-expose` label.
