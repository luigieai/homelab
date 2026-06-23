# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

Homelab infrastructure running on a single home server. The `legacy/` directory preserves old Nomad/Terraform/Ansible configs for reference — do not modify unless explicitly working on a migration task. They are NOT utilized anymore. Active development is in `docker/`.

## Architecture

**Proxmox** is the base virtualization platform with two networks:
- **Proxmox SDN** — internal network for inter-VM/container communication (10.0.0.0/24)
- **Proxmox default bridge** — LAN/WAN access (192.168.15.0/24)

Container orchestration runs on **Docker Compose** with **Traefik v3.6** as the single ingress controller. Each directory under `docker/` is an independent stack deployed with `docker compose up -d`. The homelab is conceptually organized into layers, simulating company departments:
- **Platform** — core infra (Proxmox, Docker Compose, Traefik, DNS)
- **Corporate** — governance apps (IAM/OAuth, DNS, automation, wiki)
- **Departments** — app areas isolated by domain/objective (Development, Music/DJ, Gaming, Household, etc.)

## Traefik Networking Model

Traefik runs with `network_mode: host`, meaning it shares the host's network stack and is **not** inside any Docker network. It discovers containers via the Docker socket and reaches them through the host's routing table, which has routes to every Docker bridge network automatically.

**Implication**: services do **not** need a shared network with Traefik. Each stack defines its own internal bridge network (e.g. `corporate_network`). Services only need to be on that network and have Traefik labels — Traefik will reach them directly via the host.

No pre-created host network is needed. No `traefik-public` external network. No shared network across stacks.

## Adding a New Service

Declare Traefik labels at the service top level (not under `deploy:`). Use `cloudflare` as the cert resolver. The service only needs to be on its stack's own internal network.

```yaml
services:
  myapp:
    image: myapp:latest
    restart: unless-stopped
    networks:
      - mystack_network
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.myapp.rule=Host(`myapp.app.marioverde.com.br`)"
      - "traefik.http.routers.myapp.entrypoints=websecure"
      - "traefik.http.routers.myapp.tls.certresolver=cloudflare"
      - "traefik.http.services.myapp.loadbalancer.server.port=80"

networks:
  mystack_network:
    driver: bridge
```

> **Note**: No shared external network with Traefik is required. Traefik uses `network_mode: host` and reaches all Docker bridge networks directly through the host's routing table.

**Domain pattern**: `APPNAME.app.marioverde.com.br` or `APPNAME.lab.marioverde.com.br`. They can have both domains. *.app* is for wan apps. *.lab* is for internal apps. An app can be reachable in both domains.

**Secrets**: Sensitive env vars go in `.env` (not committed). Always create a `.env.example`. Non-sensitive vars can be inline in the compose file.

## Deploy Commands

```bash
# Deploy or update a stack (run from the stack's directory)
docker compose up -d

# Tear down a stack
docker compose down

# View running containers for a stack
docker compose ps

# View all running containers on the host
docker ps
```

## Legacy Reference (do not modify)

### Terraform (Nomad jobs)

```bash
# Required before any terraform command — PostgreSQL backend
read -s PGPASSWORD && export PGPASSWORD

cd legacy/terraform-home/   # or terraform-lab/
terraform init && terraform plan && terraform apply
```

### Ansible (Server provisioning)

```bash
cd legacy/ansible-home/

# Install dependencies
ansible-galaxy install geerlingguy.pip geerlingguy.docker robertdebock.vault

# Provision
ansible-playbook newserver.yml -i ./inventory/proxmox.yml --tags "sshkey,nosudopwd,updatesystem"
ansible-playbook dockerserver.yml -i ./inventory/proxmox.yml
ansible-playbook nomadserver.yml -i ./inventory/proxmox.yml
```
