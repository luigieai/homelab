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

<!-- cce-block-version: 4 -->
## Context Engine (CCE)

This project uses Code Context Engine for intelligent code retrieval and
cross-session memory.

### Searching the codebase

**You MUST use `context_search` instead of reading files directly** when
exploring the codebase, answering questions about code, or understanding how
things work. This is a hard requirement, not a suggestion. `context_search`
returns the most relevant code chunks with confidence scores instead of whole
files, and tracks token savings automatically.

When to use `context_search`:
- Answering questions about the codebase ("how does X work?", "where is Y?")
- Exploring structure or architecture
- Finding related code, functions, or patterns
- Any time you would otherwise read a file just to understand it

When to use `Read` instead:
- You need to edit a specific file (read before editing)
- You need the exact, complete content of a known file path

Other search tools:
- `expand_chunk` — get full source for a compressed result
- `related_context` — find what calls/imports a function

### Cross-session memory — use it actively

This project has persistent memory across Claude Code sessions. **You must
use it both ways: recall before answering, record after deciding.** Memory
that is not recorded is lost; memory that is not recalled does nothing.

**Before answering a non-trivial question, call `session_recall`.**
Especially when:
- The question touches architecture, design, or naming choices
- The user asks "what / why / how did we ..."
- You are about to recommend an approach the team may have already chosen
  or already rejected

Pass a topic phrase, not a single word — e.g. `session_recall("auth flow")`,
not `session_recall("auth")`. Recall is vector-similarity-based, so paraphrases
match. If recall returns relevant entries, lead with them ("Per a prior
decision: ...") instead of re-deriving the answer.

**After making a non-obvious decision, call `record_decision`.** Especially:
- Choosing one library / pattern / approach over another
- Resolving an ambiguity in the spec or requirements
- Establishing a convention the project should follow going forward
- Anything you would not want to re-litigate next session

Format: `record_decision(decision="...", reason="...")`. Keep both fields
short and specific — they are surfaced verbatim at the start of future
sessions.

**After meaningful work in a file, call `record_code_area`.** Especially when:
- You added or substantially modified a function/class
- You traced through a non-obvious flow and want future-you to find it fast

Format: `record_code_area(file_path="...", description="...")`.

Skip recording for trivial reads, formatting changes, or one-off lookups —
the goal is durable signal, not an event log.

### Drilling deeper from a recall hit

`session_recall` results are tagged with the source session id, e.g.
`[turn sid:abc123|n:5]`. To drill in:

- `session_timeline(session_id="abc123")` — walk the per-turn summaries of
  that session in order. Use this when the user asks "what was the
  reasoning?" or "how did we get there?".
- `session_event(event_id=N)` — fetch a specific tool event's raw input
  and output (capped at 4 KB at read time). Use this when a turn summary
  references a tool result you actually need to inspect.

Both are read-only and cheap. Prefer them over re-running tool calls or
asking the user to re-paste context.

### Output style

Respond in compressed style. Drop articles (a, an, the) in prose. Use
sentence fragments over full sentences. Use short synonyms (fix not resolve,
check not investigate). Pattern: [thing] [action] [reason]. [next step].
No filler, hedging, pleasantries, trailing summaries, or restating what
the user said. One sentence if one sentence is enough.

When suggesting code changes, show only the changed lines with 3 lines of
context. Never rewrite entire files. Multiple changes in one file: show each
change separately. Never echo back unchanged code the user already has.

Code blocks, file paths, commands, error messages: always written in full.
Security warnings and destructive action confirmations: use full clarity.
<!-- /cce-block -->
