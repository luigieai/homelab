# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is a homelab infrastructure repository for managing services across two environments:
- **Home environment**: Proxmox server running Nomad with Terraform-managed services
- **Hetzner dedicated server**: Shared services with friends using Proxmox, pfSense, Traefik, and Nomad

## Architecture

### Core Infrastructure Stack
- **Proxmox**: Base virtualization platform on both environments
- **Nomad**: Container orchestration and job scheduling
- **Terraform**: Infrastructure as Code for service provisioning
- **Ansible**: Server configuration and management
- **Docker Compose**: Service orchestration for Coolify-managed applications

### Directory Structure
- `terraform-home/`: Terraform configurations for home Nomad services
- `terraform-lab/`: Terraform configurations for Hetzner lab services  
- `ansible-home/`: Ansible roles for server provisioning and configuration
- `coolify/`: Docker Compose configurations for services managed by Coolify

## Common Commands

### Terraform Operations
```bash
# Setup required environment variable for PostgreSQL backend
read -s PGPASSWORD
export PGPASSWORD

# Standard Terraform workflow
cd terraform-home/ # or terraform-lab/
terraform init
terraform plan
terraform apply
```

### Ansible Operations
```bash
cd ansible-home/

# Test connectivity (with password prompt)
ansible proxmox -i ./inventory/proxmox.yml -m ping --ask-pass --ask-become-pass

# Run specific roles with tags
ansible-playbook newserver.yml -i ./inventory/proxmox.yml --tags "sshkey,nosudopwd,updatesystem"
ansible-playbook dockerserver.yml -i ./inventory/proxmox.yml
ansible-playbook nomadserver.yml -i ./inventory/proxmox.yml
```

### Required Ansible Dependencies
```bash
ansible-galaxy install geerlingguy.pip
ansible-galaxy install geerlingguy.docker
ansible-galaxy install robertdebock.vault
```

## Service Configuration

### Home Environment Services (Nomad/Terraform)
- **Caddy**: Reverse proxy with automatic TLS via Cloudflare
- **PostgreSQL**: Database server with pgAdmin
- **Redis**: In-memory data store
- **Keycloak**: Identity provider (OAuth2/OpenID)
- **Icecast**: Audio streaming server
- **Kavita**: Self-hosted ebook server
- **TwitchMiner**: Twitch channel points automation

### Coolify-Managed Services (Docker Compose)
- **Authentik**: Identity and access management
- **Calibre Web Automated**: Ebook management
- **Glance**: Dashboard application
- **Grafana**: Monitoring and visualization

#### Docker compose example
Every docker compose needs to follow traefik configuration, here's an example of a working nginx container running within my domain:
```yaml
services:
  nginx-app:
    image: nginx:alpine
    container_name: nginx-app
    restart: unless-stopped
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.nginx-app.rule=Host(`nginx.app.marioverde.com.br`)"
      - "traefik.http.routers.nginx-app.entrypoints=websecure"
      - "traefik.http.routers.nginx-app.tls.certresolver=letsencrypt"
      - "traefik.http.services.nginx-app.loadbalancer.server.port=80"
    networks:
      - traefik

networks:
  traefik:
    external: true
```
For the domain, always follow the pattern: APPNAME.app.marioverde.com.br OR APPNAME.intranet.maiorverde.com.br. There should be cases where I use both domains for one app.
Environment variables without sensitive information should be visible on the docker compose, Environment variables with sensitive informations (examples: password, secret tokens) should be within a .env file:
```
env_file:
      - .env
```
ALWAYS generate an example of the .env called .env.example for human reading.

## Infrastructure Notes

### Network Configuration
- Home endpoint: `192.168.15.92`
- Uses Netbird VPN for secure access
- DNS provided by AdGuard
- PostgreSQL accessible at `100.64.0.7` from Docker services

### Common Setup Issues

#### PGAdmin Permissions
When deploying pgAdmin via Nomad, ensure proper directory permissions:
```bash
mkdir /alloc/pgadmin
sudo chown -R 5050:5050 /alloc/pgadmin
```

#### Terraform Backend
PostgreSQL is used as Terraform backend. Ensure PGPASSWORD environment variable is set before running Terraform commands.

## Security Considerations
- SSH key-based authentication is preferred over passwords
- Services use environment variables for secrets (never commit .env files)
- Authentik configured with proxy headers for reverse proxy compatibility
- Ansible roles include optional sudo password disabling (home lab only)