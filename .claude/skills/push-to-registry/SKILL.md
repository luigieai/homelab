---
name: push-to-registry
description: Build and push a custom scripts/<tool> image to the homelab private registry (registry.lab.marioverde.com.br), then roll it out via its docker/platform/<tool> stack. Use whenever the user asks to "push to registry", "push the image", "build and push", "publish the image", or "deploy the script/tool".
---

# Push to Registry

Builds a custom tool's Docker image from `scripts/<tool>/` and pushes it to
the homelab's private registry, so the corresponding `docker/platform/<tool>/`
stack can pull and run it. This is the standard path for anything under
`scripts/` — see root [CLAUDE.md](../../../CLAUDE.md) "Custom Tooling"
section: `docker/` never builds from source in place, it only deploys
pre-built images.

## Registry

- Host: `registry.lab.marioverde.com.br`
- No auth — anonymous push/pull enabled (internal `.lab` only, see
  [docker/platform/registry](../../../docker/platform/registry/)). Do not
  attempt `docker login`.

## Image naming convention

`registry.lab.marioverde.com.br/<tool-name>:<tag>`, where `<tool-name>`
matches the `scripts/<tool-name>/` directory name, and the corresponding
`docker/platform/<tool-name>/compose.yaml` references that exact image (check
its `image:` line / version env var to confirm before pushing — don't assume,
read it).

## Steps

1. Identify which tool to push. If not explicit, check `scripts/` for the
   directory in question and confirm with the user if ambiguous.
2. Read `docker/platform/<tool-name>/compose.yaml` to confirm the exact image
   name/tag variable it expects (e.g. `${DNS_SYNC_VERSION:-latest}` style —
   the tag you push must match what that stack will actually pull).
3. Build from the tool's own directory:
   ```bash
   cd scripts/<tool-name>/
   docker build -t registry.lab.marioverde.com.br/<tool-name>:<tag> .
   ```
4. This is a real, externally-visible publish to shared infrastructure —
   confirm with the user before pushing, unless they've already explicitly
   asked for this push in the current turn.
5. Push:
   ```bash
   docker push registry.lab.marioverde.com.br/<tool-name>:<tag>
   ```
6. Report the resulting digest (`docker push` output ends with
   `<tag>: digest: sha256:...`) so the user can verify what shipped.
7. Rollout is a separate, also-confirm-first step (don't chain automatically
   unless asked): in `docker/platform/<tool-name>/`,
   ```bash
   docker compose pull
   docker compose up -d
   ```

## Known tools

| Tool | Source | Deployment | Registry image |
|---|---|---|---|
| dns-sync | [scripts/dns-sync/](../../../scripts/dns-sync/) | [docker/platform/dns-sync/](../../../docker/platform/dns-sync/) | `registry.lab.marioverde.com.br/dns-sync:<tag>` (tag via `DNS_SYNC_VERSION` env var, default `latest`) |

Add a row here after onboarding a new `scripts/<tool>` so this table stays
the quick reference instead of re-deriving it from the directory tree each
time.
