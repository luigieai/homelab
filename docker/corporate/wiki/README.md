# Wiki.js 3

Knowledge base / documentation wiki (Corporate layer).

| | |
|---|---|
| Image | `ghcr.io/requarks/wiki` — 3.0.0-beta, pinned via `WIKI_VERSION` |
| URL | <https://wiki.lab.marioverde.com.br> (LAN + Tailscale only, no WAN record) |
| Database | PostgreSQL 18 on CT 103 (`10.0.0.2`), database `wiki`, role `wikijs` |
| Deployed by | Komodo stack `wiki`, run directory `docker/corporate/wiki`, branch `master` |

## Deploy

Push to `master`, then from the komodo skill directory on the Hermes CT:

    python3 scripts/komodo.py deploy-stack wiki

## Database (one-off)

    CREATE ROLE wikijs LOGIN PASSWORD '<generated>';
    CREATE DATABASE wiki OWNER wikijs;
    \c wiki
    CREATE EXTENSION IF NOT EXISTS ltree;
    CREATE EXTENSION IF NOT EXISTS pg_trgm;

`ltree` and `pg_trgm` are required by Wiki.js and are created as the superuser so the app never needs
to.

## Secrets

The repo is public: nothing sensitive is committed. Komodo writes `.env` from the stack's
**Environment** settings — `WIKI_VERSION`, `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASS`,
`ADMIN_EMAIL`, `ADMIN_PASS`, `LOG_LEVEL` (see `.env.example`).

## First boot

`ADMIN_EMAIL` / `ADMIN_PASS` create the root administrator only while no root admin exists. Change that
password on first login; it stays a local login as the emergency door, SSO included.

## Behind Traefik

Enable **Administration → Security → Trust X-Forwarded-* Proxy Headers**. Without it Wiki.js builds
absolute URLs as `http://<container>`, which breaks the OIDC callback. WebSocket upgrades
(live collaboration, `/_collab`) pass through Traefik unchanged.

## SSO (authentik)

**Administration → Authentication → Generic OpenID Connect / OAuth2**:

| Setting | Value |
|---|---|
| Client ID / Secret | from the authentik provider |
| Issuer | `https://auth.lab.marioverde.com.br/application/o/wiki/` |
| Use Discovery | on |
| Scopes | `openid profile email` |
| Map Groups / self-registration | off (the admin account already exists) |

The authentik side is an OAuth2/OpenID provider + application pair; see
`integrations.goauthentik.io/documentation/wiki-js/`.

## Upgrade

Bump `WIKI_VERSION` in the stack environment (and in `.env.example`), then `PullStack` + `DeployStack`.
Migrations run on boot. Betas change; pin, never float.

## Rollback

    python3 scripts/komodo.py stop-stack wiki

and, to remove the data too, on CT 103: `DROP DATABASE wiki; DROP ROLE wikijs;`.
