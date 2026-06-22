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

## One-Time Host Setup

Before deploying any stack, create the shared Traefik network on the host:

```bash
docker network create traefik-public
```

This bridge network is shared across all stacks. Run this once. If the host reboots and the network is lost, recreate it before bringing stacks back up.

## Adding a New Service

All services that need Traefik routing must join the `traefik-public` bridge network and declare Traefik labels at the service top level (not under `deploy:`). Use `cloudflare` as the cert resolver.

```yaml
services:
  myapp:
    image: myapp:latest
    restart: unless-stopped
    networks:
      - traefik-public
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.myapp.rule=Host(`myapp.app.marioverde.com.br`)"
      - "traefik.http.routers.myapp.entrypoints=websecure"
      - "traefik.http.routers.myapp.tls.certresolver=cloudflare"
      - "traefik.http.services.myapp.loadbalancer.server.port=80"

networks:
  traefik-public:
    external: true
    name: traefik-public
```

> **Note**: The `name: traefik-public` must match the pre-created host network exactly. Without the explicit `name`, Docker will create a per-stack network and Traefik will not find the containers.

**Domain pattern**: `APPNAME.app.marioverde.com.br` or `APPNAME.lab.marioverde.com.br`. They can have both domains. *.app* is for wan apps. *.lab* is for internal apps. An app can be reachable in both domains.

**Secrets**: Sensitive env vars go in `.env` (not committed). Always create a `.env.example`. Non-sensitive vars can be inline in the compose file.

## Deploy Commands

```bash
# One-time host setup (recreate after host reboot if the network is gone)
docker network create traefik-public

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
