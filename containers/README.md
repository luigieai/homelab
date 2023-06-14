# Containers
This folder contain the docker declaration for my homelab changes using portainer, when using Stack option at portainer, you can import a docker compose file from a git repository source and automatically pull changes from the git source.
**TODO**: Explain how to setup this process

## Services
Here the list of the services that I'm running at my homelab:

### wg-easy
Link: *https://github.com/wg-easy/wg-easy/*

I use wg-easy for managing the wireguard environment at my homelab, I want a VPN for some reasons:
- Access my homelab from outside my LAN, so if I need to manage any service I can easily do without the need to expose everything for the internet.
- Maybe If i'm in a insecure network, proxy my home internet with VPN for secure access
- Sometimes my friend have trouble to play an online game because of routing problems from their ISPs, I can proxy my connection to them aswell.

**Variables**
There's some sensitive variables, we should configure directly in portainer these: 
```yaml
- PASSWORD=<insert password to access the admin painel>
```

### AdGuard Home
Link: *https://github.com/AdguardTeam/AdGuardHome*

I use AdGuard home for it's own purpose: safe browsing at DNS Level, also I'm actually using it as my local dns resolver for all my homelab

**Variables** 
You can configure everything on it's own UI accessing at port 3000

### Nginx proxy manager
Link: *https://nginxproxymanager.com/*
A nice and simpler nginx configuration UI for our homelab. We take advantage of our DNS sponsored by AdGuard and all servers and containers of my homelab can now be accessed by a cool domain

**Variables** 
setup at port 81, for the fist time the default credentials are: 
```
Email:    admin@example.com
Password: changeme
```

