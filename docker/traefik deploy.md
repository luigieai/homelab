# Traefik — Service Integration Guide (Docker Swarm)

## How it works

Traefik is deployed as a global Swarm service and watches for services that opt in via labels.
All traffic routing is configured through labels on each service's `deploy.labels` block.

The overlay network `traefik-public` (stack-prefixed as `traefik_traefik-public` at runtime) is the shared bridge between Traefik and your services.

---

## Checklist for every new service

### 1. Attach the service to the `traefik-public` network

Each service must declare the external network and attach to it:

```yaml
networks:
  traefik-public:
    external: true

services:
  myapp:
    ...
    networks:
      - traefik-public
```

> Do **not** redefine the network — it must be `external: true` so it reuses the one created by the Traefik stack.

### 2. Add the required labels under `deploy.labels`

```yaml
deploy:
  labels:
    - "traefik.enable=true"

    # Router: match incoming hostname
    - "traefik.http.routers.myapp.rule=Host(`myapp.lab.marioverde.com.br`)"
    - "traefik.http.routers.myapp.entrypoints=websecure"
    - "traefik.http.routers.myapp.tls.certresolver=cloudflare"

    # Service: tell Traefik which port the container listens on
    - "traefik.http.services.myapp.loadbalancer.server.port=3000"

    # Network: must match the runtime-prefixed name of the Traefik stack's network
    - "traefik.swarm.network=traefik_traefik-public"
```

Replace `myapp` with a unique name for each service, and `3000` with the container's actual port.

> **Why `traefik.swarm.network`?**
> When `docker stack deploy` creates the overlay network, it prefixes it with the stack name.
> Traefik's global default (`traefik-public`) doesn't match the actual name (`traefik_traefik-public`),
> so this label must be set explicitly on every service to avoid routing to the wrong network.

### 3. Deploy the service as a stack

```bash
docker stack deploy -c compose.yaml <stack-name>
```

---

## Minimal example

```yaml
services:
  myapp:
    image: myapp:latest
    networks:
      - traefik-public
    deploy:
      labels:
        - "traefik.enable=true"
        - "traefik.http.routers.myapp.rule=Host(`myapp.lab.marioverde.com.br`)"
        - "traefik.http.routers.myapp.entrypoints=websecure"
        - "traefik.http.routers.myapp.tls.certresolver=cloudflare"
        - "traefik.http.services.myapp.loadbalancer.server.port=3000"
        - "traefik.swarm.network=traefik_traefik-public"

networks:
  traefik-public:
    external: true
```

---

## Common mistakes

| Mistake | Result |
|--------|--------|
| Labels under `services.<name>.labels` instead of `deploy.labels` | Traefik ignores them in Swarm mode |
| Missing `traefik.swarm.network` label | Warning in logs, may route to wrong network |
| Network not declared as `external: true` | Docker creates a duplicate isolated network |
| `traefik.enable=true` missing | Service is ignored by Traefik |
| Wrong port in `loadbalancer.server.port` | 502 Bad Gateway |
