# Containers
This folder contain the docker declaration for my homelab changes using portainer, when using Stack option at portainer, you can import a docker compose file from a git repository source and automatically pull changes from the git source.
**TODO**: Explain how to setup this process

## Services
Here the list of the services that I'm running at my homelab:

### VPN with wireguard
Link: *https://github.com/ngoduykhanh/wireguard-ui*

I use wireguard with wireguard-ui for managing the wireguard environment at my homelab, I want a VPN for some reasons:
- Access my homelab from outside my LAN, so if I need to manage any service I can easily do without the need to expose everything for the internet.
- Maybe If i'm in a insecure network, proxy my home internet with VPN for secure access
- Sometimes my friend have trouble to play an online game because of routing problems from their ISPs, I can proxy my connection to them aswell.

**Variables**
All the variables can be change in the wireguard-ui later, so for now we start the container with admin/admin credentials for first time setup