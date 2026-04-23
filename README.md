# Homelab repo

This is the repository for all my automations and notes for my homelab. My homelab runs on a single home server.

## Infrastructure

The base is **Proxmox Community Edition** with the following network setup:
- **Proxmox SDN** — internal network for inter-VM/container communication (10.0.0.0/24)
- **Proxmox default bridge** — LAN access from home network, later WAN access from VPN routing (192.168.15.0/24)

## Architecture

The homelab is organized into layers, simulating companies departments:

### Platform
Base infrastructure — the most critical and sensitive pieces. Everything else depends on it.

- **Proxmox** — host virtualization
- **Docker Swarm** — container orchestration
- **Traefik** — reverse proxy and TLS termination (via Cloudflare DNS challenge). hosted on docker swarm.

### Corporate
Apps that govern and organize the lab: IAM/OAuth provider, DNS, automation, wiki/docs. All other services should integrate with these.

- **CoreDNS** - Hosted in a LXC Container, terminates the domain for local access

### Departments
Apps organized by area/objective, each isolated by domain and purpose (**Active development**): 
- Development 
- Music/DJ
- Gaming servers
- Household
- stil deciding...

## Currently Deployed

- **Traefik v3.6** — ingress for the Docker Swarm, dashboard at `traefik.lab.marioverde.com.br`
- **CoreDNS** - Hosted in a LXC Container, terminates the domain for local access.
- **lldap** - User management for corporate dept. `lldap.lab.marioverde.com.br`
- **authentik** - User oauth management for corporate dept. `auth.lab.marioverde.com.br`
## Domain Pattern

- `APPNAME.app.marioverde.com.br` = Apps that will be deployed in WAN
- `APPNAME.lab.marioverde.com.br` - Apps deployerd both in LAN and Internal network. 
