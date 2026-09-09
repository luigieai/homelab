# SteamAuth

Deploys prebuilt images from the internal registry:
- `registry.lab.marioverde.com.br/steamauth-backend:latest` (NestJS API + SQLite)
- `registry.lab.marioverde.com.br/steamauth-frontend:latest` (Nuxt 4 UI)

Source repo: SteamAuthWeb (monorepo, `steam-auth-web/` = backend, `frontend/` = frontend).

## Routes

- Frontend: `https://steamauth.lab.marioverde.com.br`
- Backend: `https://steamauth-api.lab.marioverde.com.br` — has its own Traefik hostname (not internal-only) because the OIDC login flow redirects the user's **browser** to the backend directly (`/auth/oidc/login`, `/auth/oidc/callback`). The frontend also calls the backend through this same public hostname (`NUXT_PUBLIC_API_BASE_URL`), since that value is shared between server-side (SSR) and client-side (browser) code in Nuxt — it can't point at the internal `http://backend:3000` Docker hostname, or OIDC login links break with an unreachable redirect.

## Deploy

```bash
cp .env.example .env
# edit .env: set JWT_SECRET, NUXT_SESSION_PASSWORD, and OIDC vars if using SSO
docker compose up -d
```

## Data directory permissions (required before first run)

The backend image runs as an unprivileged `node` user (uid 1000) and writes its SQLite database to `/app/data`. Since `./data` is a bind mount, Docker creates it as root on the host by default, which blocks the container from opening the database (`SQLITE_CANTOPEN`).

Before first deploy (or if `./data` ever gets recreated as root), run on the host:

```bash
mkdir -p ./data && chown -R 1000:1000 ./data
```

If deploying via Komodo, this is set as a **Pre Deploy** command on the stack so it runs automatically before every `docker compose up`.

## OIDC / Authentik setup

Backend uses Authorization Code + PKCE against any OIDC-compliant provider. To wire up Authentik (`auth.lab.marioverde.com.br`):

1. **Provider** (Applications → Providers → OAuth2/OpenID Provider):
   - Client type: Confidential
   - Redirect URI: `https://steamauth-api.lab.marioverde.com.br/auth/oidc/callback` (must match `OIDC_REDIRECT_URI` exactly)
   - Scopes: `openid email profile` (Authentik defaults cover this)
2. **Application** (Applications → Applications):
   - Slug: `steamauth` — determines the issuer URL path
   - Provider: the one created above
3. Set in `.env`:
   ```
   OIDC_ISSUER_URL=https://auth.lab.marioverde.com.br/application/o/steamauth/
   OIDC_CLIENT_ID=<from provider>
   OIDC_CLIENT_SECRET=<from provider>
   OIDC_REDIRECT_URI=https://steamauth-api.lab.marioverde.com.br/auth/oidc/callback
   OIDC_FRONTEND_CALLBACK_URL=https://steamauth.lab.marioverde.com.br/api/auth/oidc/callback
   ```

Leave `OIDC_ISSUER_URL`/`OIDC_CLIENT_ID` blank to disable SSO — local email/password login still works.

## Host DNS note

`registry.lab.marioverde.com.br` (and other internal hostnames) must resolve from whatever host actually runs `docker compose pull` — this is the host OS's own `/etc/resolv.conf`, not just `dockerd`'s `daemon.json` `dns` key (that field only configures DNS *inside containers Docker creates*, not the daemon's own outbound pulls). On this LXC, Tailscale manages `/etc/resolv.conf` via MagicDNS — confirm with `getent hosts registry.lab.marioverde.com.br` if a pull ever fails with a DNS lookup error.

## Troubleshooting

- **`SQLITE_CANTOPEN` on backend startup**: fix `./data` ownership, see above.
- **OIDC login redirects to `http://backend:3000/...`**: `NUXT_PUBLIC_API_BASE_URL` in `compose.yaml` was pointed at the internal Docker hostname instead of the public backend URL — must be `https://steamauth-api.lab.marioverde.com.br`.
- **Image pull fails with a DNS lookup error**: see Host DNS note above; check resolution from the host itself, not just inside a container.
