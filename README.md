# Homelab repo

This is the repository for all my automations and notes for my homelab, more details soon, for now you can check more about the ansible playbooks in their respective readme

# What I host?
Here is everything I currently host, infrastructure part it's the machines and services part all my apps.
## Infrastructure
My host machine is hosting proxmox community edition, and it's the base for everything, where I have these virtual machines:
- CSGO
- TeamSpeak
- Containers (Docker server controlled by portainer)

## Services
Right now I'm hosting:

### DNS Server
I'm using AdGuard for DNS hosting, it's a good substitute for pi-hole and while it's not a full dns server at his heart, the DNS Rewrite function enable me using local dns addresses properly, and I don't need anything more for now.

### VPN
I'm using Wireguard with WG-Easy for VPN, but I found out that wg easy is pretty simple for what I need to do, I wanna setup multiple interfaces for wireguard, so I could make differents groups for VPN with multiple access types (example: for one group wireguard will handle all traffic, for other group only internet but not LAN, for other group LAN etc etc), so I'm thinking if I will maintain my own fork of wg-easy that runs easily in container, or if I provision a new VM only for wireguard and can use another UI or handle users with ansible.

### Nginx
Nginx is my official gateway, I'm using nginx-proxy-manager because it's simple and provide a nice UI, don't need everything more. With DNS Server all of my services is acessible locally with easy addresses to remember

### Portainer
For my docker deployments, I use portainer and for the docker services I use this own repo for deploying via GitOps, you can check it out my deployment [here](./ansible/)

### Teamspeak server
I host a teamspeak server where I use daily with my friends.
### Gaming servers
Inside CSGO virtual machine, I host a server of counter strike global offensive and project zomboid, both servers are private and for friends only. Usually I shutdown a server while another is running because of resources, but they can run at same time aswell.
# Where I host?

Currently I'm hosting at my house, server specs coming soon!