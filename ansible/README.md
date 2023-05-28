# Ansible
Ansible roles for managing my proxmox servers, as I use personally for my homelab, if you want to use by yourself some changes will be needed, I'll try to write to make the process easier but maybe I will leave some gaps.

## For new servers
Please, configure a user with ssh access, I prefeer using ssh keys but you can use password aswell, just configure the variabel in ./inventory folder. In this case we're using 'luigi' for username, because it's my default user in my homelab.

Example with asking password:
```shell 
ansible proxmox -i ./inventory/proxmox.yml -m ping --ask-pass --ask-become-pass
```

I created the *newserver* role for when a empty linux is running, I run ubuntu 22.04 so I consideer only this distro supported for now. This role has following tags
- sshkey
- nosudopwd
- updatesystem

**WARNING THIS ROLE CAN REBOOT YOUR SERVER**

### SSH *(ssh.yml)*
This task searches the *id_rsa.pub* file inside the machine that is running the playbook, and add the public key to the remote servers defined in inventory, uses *ansible_user* as variable, maybe you want to change to another variable.

### Update system packages *(update.yml)*
Update cache and repo for apt repositories in the system, reboot the server if is needed.

### Disable sudo password *(nosudopwd.yml)*
**NOT RECOMMENDED FOR CORPORATE OR INTERNET EXPOSED SERVERS**
Disable sudo password prompt when using the command, as my servers are not exposed I disable this for automations purposes

## Docker Server
This role has the purpose to setup my docker server infrastructure, I've choosen to switch from k8s to portainer & gitops for orchrestration. So we're using [Portainer Community Edition](https://docs.portainer.io/start/install-ce)
### Prequisites
For using this role, please install beforehand [ansible-docker-role from geergling guy](https://github.com/geerlingguy/ansible-role-docker), and [pip role](https://github.com/geerlingguy/ansible-role-pip) so we can manage docker containers with ansible: 

```shell
ansible-galaxy install geerlingguy.pip
ansible-galaxy install geerlingguy.docker
```

### Portainer
The role will install Docker + Portainer, we recommend using the role in **root** user as recommended in [portainer documentation](https://docs.portainer.io/start/install-ce/server/docker/linux#introduction).
After running the playbook, access your portainer instance using *yourhostname.tld:9443*