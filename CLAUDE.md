# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

Homelab infrastructure running on a single home server. The `legacy/` directory preserves old Nomad/Terraform/Ansible configs for reference — do not modify unless explicitly working on a migration task. They are NOT utilized anymore. Active development is in `docker/`.

## Architecture

**Proxmox** is the base virtualization platform with two networks:
- **Proxmox SDN** — internal network for inter-VM/container communication (10.0.0.0/24)
- **Proxmox default bridge** — LAN/WAN access (192.168.15.0/24)

Container orchestration runs on **Docker Swarm** with **Traefik v3.6** as the single ingress controller. The homelab is conceptually organized into layers, simulating company departments:
- **Platform** — core infra (Proxmox, Docker Swarm, Traefik, DNS)
- **Corporate** — governance apps (IAM/OAuth, DNS, automation, wiki)
- **Departments** — app areas isolated by domain/objective (Development, Music/DJ, Gaming, Household, etc.)

## Adding a New Service to the Swarm

All services must join the `traefik-public` overlay network and declare Traefik labels under `deploy.labels` (not top-level `labels`). Use `cloudflare` as the cert resolver.

```yaml
services:
  myapp:
    image: myapp:latest
    networks:
      - traefik-public
    deploy:
      labels:
        - "traefik.enable=true"
        - "traefik.http.routers.myapp.rule=Host(`myapp.app.marioverde.com.br`)"
        - "traefik.http.routers.myapp.entrypoints=websecure"
        - "traefik.http.routers.myapp.tls.certresolver=cloudflare"
        - "traefik.http.services.myapp.loadbalancer.server.port=80"
        - "traefik.swarm.network=traefik_traefik-public"  # required in Swarm mode

networks:
  traefik-public:
    external: true
    name: traefik_traefik-public
```

> **Note**: The `name: traefik_traefik-public` is required. Docker Swarm prefixes network names with the stack name, so the network declared as `traefik-public` in the `traefik` stack becomes `traefik_traefik-public`. Without the explicit `name`, other stacks referencing it as `external: true` will fail with "network not found".

**Domain pattern**: `APPNAME.app.marioverde.com.br` or `APPNAME.lab.marioverde.com.br`. They can have both domains. *.app* is for wan apps. *.lab* is for internal apps. An app can be reachable in both domains.

**Secrets**: Sensitive env vars go in `.env` (not committed). Always create a `.env.example`. Non-sensitive vars can be inline in the compose file.

## Deploy Commands

```bash
# Deploy or update a stack
docker stack deploy -c compose.yaml <stack-name>

# Remove a stack
docker stack rm <stack-name>

# List running stacks/services
docker stack ls
docker service ls
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
