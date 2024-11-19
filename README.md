# Homelab repo

This is the repository for all my automations and notes for my homelab. Right now my homelab is running on two machines, one at my home and one at a hetzner dedicated server.

# What I host home?
Here is everything I currently host, infrastructure part it's the machines and services part all my apps.
## At home
My home machine is hosting proxmox community edition, and it's the base for everything, where I have a few virtual machines. I give acess to my home machine using [my script for DDNS](https://github.com/luigieai/ddns-cloudflare-shell), as my domain is hosted in cloudflare.

## Terraform
I'm using nomad + terraform for automatic provisioning of my services. Everything I change or create I commit to the repo, and terraform will create the resources.

## Services
I have a nomad server running on my home machine, it's a single node server, and I'm using it for running containers, and for running some services that I need.
Right now I'm hosting:

### DNS Server
I'm using AdGuard for DNS hosting, it's a good substitute for pi-hole and while it's not a full dns server at his heart, the DNS Rewrite function enable me using local dns addresses properly, and I don't need anything more for now.

### VPN
Right now I'm using [netbird](https://netbird.io/) for VPN, it's a good because uses wireguard, and it's easy to setup and use. But with my dedicated server In hetzner, probably I will switch to headscale later.

### Caddy
Caddy is my reverse proxy, with terraform I can easily deploy new endpoints with TLS for my local network.

### Icecast
I'm using icecast for streaming my live DJs sets for my friends.

### Kavita
Kavita is my self-hosted ebooks server. Right I'm importing them manually and I will probably see If I will migrate this service to my dedicated server in hetzner.

### Keycloak
Keycloak is my identity provider, I'm using it for my local projects as I usually use openID and oauth2 for authentication. Right now there's no service in the homelab using it but it's very useful in my development enviroment.

### PostgreSQL
I'm using a single node postgres server for the lab services and my personal projects. The job also has a pgAdmin instance running.

### Redis
Right now I'm using redis for nothing.

### TwitchMiner
My instnace of [Twitch-Channel-Points-Miner-v2](https://github.com/rdavydov/Twitch-Channel-Points-Miner-v2)

# What I host in hetzner?
At hetzner I "share" some personal services with my friends projetcs. But the basic infrascructure is running proxmox with NAT for an instance of pfSense for router. A traefik in a LXC for reverse proxy. And a nomad server with some jobs for running containers.