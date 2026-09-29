# devws — user manual

> **Canonical copy:** this file lives in the `homelab` repo (`docs/devws-manual.md`). Edit it here.
> `/root/devws/MANUAL.md` is only a pointer.

Everything in here is about **CT 300 (`luigi-devworkspace`)**, your dev box. It is written for you,
not for an agent: it is the "how do I actually use this day to day" document. The terse version lives
in `README.md`; the acceptance suite lives in `tests/selftest.sh`.

---

## 1. What this setup is, in 30 seconds

Two coding harnesses live on CT 300 and they play different roles:

| | Harness | Model | Role | Auth |
| --- | --- | --- | --- | --- |
| **Planner** | Claude Code (`claude`) | sonnet, plan mode (read-only) | reads the repo, writes the plan | your Claude Pro subscription (OAuth) |
| **Executor** | DeepSeek Harness (`dsh`) | `deepseek-flash` | executes the plan: edits files, runs commands, commits | your DeepSeek key |

`devws` is the wrapper around both. It is the only thing that knows how to run them, so learning
`devws` is the whole job. It works the same whether *you* type it over SSH or **Hermes** runs it for you.

You keep your own hands-on path (VSCode + the Claude Code extension) — that is unchanged and always
available. `devws` is for when you want the loop to run without you babysitting it.

---

## 2. Where things live

| Path (CT 300) | What |
| --- | --- |
| `/root/workspace/<repo>` | your repos: `homelab`, `twitch-mv`, `SteamAuthWeb`, `poe-auto-teleport`, `love-letter-site` |
| `/usr/local/bin/devws` | the wrapper (symlink to `/root/devws/bin/devws`) |
| `/root/devws/bin/devws` | the wrapper source (git repo, versioned) |
| `/root/devws/prompts/planner.md` | what Claude is told before planning |
| `/root/devws/prompts/executor.md` | the executor's house rules |
| `/root/devws/tests/selftest.sh` | 22 end-to-end assertions |
| `/root/devws/plans/` | every plan ever written (`<repo>-<timestamp>-<slug>.md`) |
| `/root/devws/logs/` | every execution log (`<repo>-<timestamp>.exec.log`) |
| `/root/.dsh/.env` | the harness DeepSeek key (interactive use) |
| `/root/.config/devws/automation.env` | the harness DeepSeek key + safety env (automated runs) |
| `/root/.dsh/profiles/headless/` | the executor profile (model, permissions, cce MCP server) |

Pinned versions today: Claude Code `2.1.284`, dsh `0.1.7-rc.2`, cce `0.4.26`, node `v26.5.0`,
bubblewrap `0.12.0`, tmux `3.5a`.

---

## 3. Your three ways to work

### A. Hands-on in VSCode (what you already do)

1. VSCode → Remote-SSH → `root@100.92.103.52` (Tailscale) or your usual host entry.
2. Open `/root/workspace/<repo>`.
3. Code with the Claude Code extension as before. `claude` on the PATH is now also available in the
   integrated terminal if you want the CLI instead of the panel.

Nothing about this path changed. Use it when you want to be in the driver's seat.

### B. The `devws` loop (plan in one harness, execute in the other)

```bash
cd /root/workspace/homelab
devws run . "add a make target that validates every compose file"
```

That single command: Claude plans → DeepSeek executes → you get a branch with commits. If you want to
**review the plan before it runs** (recommended for anything non-trivial):

```bash
devws plan . "add a make target that validates every compose file"    # prints the plan path
less /root/devws/plans/homelab-20260929-053012-add-a-make-target-that.md
devws exec . /root/devws/plans/homelab-20260929-053012-add-a-make-target-that.md
```

Long runs: put it in tmux (`tmux new -s devws`) so a dropped VSCode/SSH connection doesn't kill it.

### C. Ask Hermes (this chat)

Say **what** and **where**, e.g. *"in twitch-mv, add rate limiting to the /login route"*. Hermes will:

1. write the plan with Claude (read-only) and read it back,
2. sanity-check the plan against the repo before spending tokens,
3. execute it with DeepSeek on a `devws/…` branch,
4. **verify** — read the diff, the commit list and the repo's own tests over SSH — and report the real
   output, including anything that failed.

What Hermes will **not** do: write repo code itself, push anything, or commit your work-in-progress for
you. If the plan looks vague it is supposed to reject it and re-plan instead of executing garbage.

---

## 4. The daily loop, in detail

```bash
ssh devworkspace                       # from your laptop, or just use the VSCode terminal
cd /root/workspace/<repo>
git status                             # clean? if not, see §5
devws status                           # versions, keys, which repos are dirty
devws run . "<request>"
```

When it finishes you get a line like:

```
DEVWS-EXEC-OK plan=/root/devws/plans/homelab-20260929-053012-….md branch=devws/20260929-053012-… log=/root/devws/logs/homelab-20260929-053012.exec.log
```

Then review and decide:

```bash
git log --oneline -5                   # the executor's commits, Conventional Commits
git diff master..HEAD                  # exactly what changed
git status -sb                         # confirm: no upstream, nothing pushed
make <whatever>                        # or the repo's own tests — run them yourself
```

Three endings, your choice:

```bash
git checkout master && git merge devws/20260929-053012-…     # keep it
git checkout master && git branch -D devws/20260929-053012-… # throw it away
git branch -m devws/20260929-053012-… my-nicer-name          # keep, but rename
```

The branch is the unit of work, so nothing lands in `master`/`main` until you say so.

---

## 5. The safety model (why it can't wreck your day)

* **Dirty tree = refuse.** `devws exec` exits `5` if the repo has uncommitted changes. It will never
  mix its commits with your WIP. Commit or `git stash` first.
* **Branch, not your branch.** Every task gets `devws/<timestamp>-<slug>`, created from wherever you
  are. Your checkout moves to that branch — that is the one side effect to expect.
* **Commit only.** The executor is told to commit per logical unit and never to push, and the harness
  enforces it: automated runs execute with `GIT_SSH_COMMAND=/bin/false` and `GIT_TERMINAL_PROMPT=0`, so
  any remote operation fails instead of silently publishing.
* **Sandboxed.** `dsh` runs with `permission.defaultPreset: workspace-write` under bubblewrap: writes
  stay in the repo, and commands are not run "unconfined" (which is why bubblewrap is installed).
* **Machine-checked finish.** The executor must end its reply with `DEVWS-EXIT: OK` or `DEVWS-EXIT: BLOCKED`.
  Exit `4` means "it stopped without saying" — treat that as suspicious and read the log.
* **22 assertions.** `devws selftest` proves the whole chain including the guards. Run it after any
  upgrade, or whenever something smells off. It takes ~1.5 minutes.

---

## 6. Project memory (cce) — the part that makes it get better

`cce` (code-context-engine) indexes each repo and keeps a memory of past sessions, decisions and turns.
Both harnesses use it:

* **You/Claude** via the hooks in `.claude/settings.json` (unchanged from before).
* **The executor** via MCP tools it now has natively: `mcp__cce__session_recall` (past decisions),
  `mcp__cce__context_search` (semantic code search), `mcp__cce__record_decision` and
  `mcp__cce__record_code_area` (writes back what it learned).

That last part is new and useful: the executor is the first thing that *records decisions* in your
memory, which means Claude's next session starts better informed.

Read the memory yourself any time:

```bash
cd /root/workspace/<repo>
cce sessions export | head -40     # decisions + turn summaries
cce sessions status                # counts, db size, health
cce search "traefik labels" --top-k 5
```

(Ollama is stopped; cce uses local embeddings and works fine. The `pthread_setaffinity` warnings in
`cce search` are noise.)

---

## 7. Keys and what bills where

| Key | Used by | Where |
| --- | --- | --- |
| DeepSeek (harness) | `dsh` everywhere on CT 300 — interactive *and* automated | `/root/.dsh/.env`, `/root/.config/devws/automation.env` |
| DeepSeek (Hermes) | this chat's agent, on CT 301 | Hermes profile `.env` |
| Anthropic (Claude Pro OAuth) | the planner and your VSCode sessions | `~/.claude/.credentials.json` |

So the split is exactly what you asked for: **Hermes spends its own key, the harness spends yours.**
Because dsh resolves credentials as *process env → `~/.dsh/.credentials.yaml` → repo `.env` →
`~/.dsh/.env`*, automated runs (which get the process env from `automation.env`) always use their own
copy — the selftest asserts this by feeding a bogus key and requiring a loud failure.

Rotating a key: edit the one line in both files, then `devws selftest --only status`. No restart needed;
dsh reads it per run.

---

## 8. The DeepSeek Web UI (your personal harness)

```bash
dsh web --port 3080 --no-open      # on CT 300 (put it in tmux)
ssh -N -L 3080:127.0.0.1:3080 root@100.92.103.52    # from your laptop, or VSCode Ports panel → 3080
```

Open the `http://127.0.0.1:3080/?token=…` URL that `dsh web` prints. The server refuses to bind
`0.0.0.0` **by design** — never expose it, always forward the port. Without the token the root returns
`401`; the token URL redirects (`303`) into a browser session, which is the handoff you want.

Quick one-off tasks without the UI:

```bash
dsh --profile headless "find every place we hardcode the domain and list the files"
```

---

## 9. Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| `devws exec` exits **5**, "working tree is dirty" | uncommitted work in the repo | `git add -A && git commit` or `git stash` |
| Planner exits **3**, "Not logged in" | Claude Pro OAuth refresh expired | `devws login-help` → run `claude`, `/login`, then `devws selftest --only plan` |
| Executor exits **6** / `DEVWS-EXIT: BLOCKED` | it stopped on purpose, usually a missing dependency or a sandbox denial | read `tail -40 /root/devws/logs/<repo>-<ts>.exec.log` |
| Executor exits **4** | dsh exited 0 without the sentinel — unsure what happened | read the log; treat the result as unverified |
| Exit **7** | key file missing/empty | check `/root/.config/devws/automation.env` |
| dsh "refusing to run the command unconfined" | bubblewrap missing after an OS change | `apt-get install -y bubblewrap` |
| `devws selftest` fails on the cce slice | cce MCP/plugin wiring | `dsh --profile headless --dump-config \| grep -A9 mcp-cce`; restore `/root/.dsh/profiles/headless/cordis.patch.yml.bak-pre-cce` if needed |
| Web UI page blank | wrong port/token, or the server died with its terminal | restart in tmux, reopen the printed token URL |
| A repo you don't care about is dirty | `poe-auto-teleport` (12), `twitch-mv` (20) normally are | `devws status` shows it; commit/stash before using the loop there |

---

## 10. Exit codes (memorise these four)

| Code | Meaning |
| --- | --- |
| `0` | success (sentinel `DEVWS-EXIT: OK` seen) |
| `1` | the executor ran but failed |
| `3` | the planner failed |
| `4` | no sentinel — outcome unknown, read the log |
| `5` | dirty working tree, refused |
| `6` | executor reported `BLOCKED` |
| `7` | key/env file missing |

---

## 11. Maintenance

```bash
devws status                     # versions + keys + repo state, always start here
devws selftest                   # 22 assertions, ~1.5 min
devws selftest --only cce        # fast check that the executor + memory still work
```

* **Upgrades**: versions are pinned deliberately (`claude 2.1.284`, `dsh 0.1.7-rc.2`). To bump: install
  the new version with `npm i -g …@<version>`, keep the old profile tree
  (`~/.dsh/profiles.bak-0.1.5` is the previous one), then run `devws selftest` and
  `dsh --profile headless --dump-config` before trusting it. dsh is a developer preview: expect churn.
* **Backups**: `/root/devws` is a git repo — commit before editing the wrapper or prompts. Plans and
  logs are regenerable, the prompts are not.
* **Rollback** (if you ever want the old world): remove the `/usr/local/bin` shims
  (`devws`, `claude`, `dsh`, `node`, `npm`, `npx`), `mv /root/devws /root/devws.bak`, and restore
  `~/.dsh/profiles` from `profiles.bak-0.1.5`. Your VSCode + extension workflow is untouched by all of it.

---

## 12. Cheat sheet

```bash
# the loop
devws status                                    # where am I: versions, keys, dirty repos
devws run . "<request>"                         # plan + execute
devws plan . "<request>"                        # plan only → prints the .md path
devws exec . /root/devws/plans/<file>.md        # execute an existing plan
devws selftest [--only cce|plan|exec|guards]    # prove it still works

# after a run
git log --oneline -5 && git diff master..HEAD   # review
git checkout master && git merge devws/<branch> # keep
git checkout master && git branch -D devws/<br> # discard

# your personal harness
dsh web --port 3080 --no-open                   # + port-forward 3080
dsh --profile headless "<one-off task>"
claude                                          # interactive Claude Code

# memory
cce sessions export | head -40                  # decisions + turns
cce search "<query>" --top-k 5

# help
devws web          # how to reach the Web UI
devws login-help   # what to do when Claude auth expires
```

**The one habit that matters:** read the plan before you let it execute, and read the diff before you
merge. The harness is built to make both cheap — the plan is a file, the work is a branch, and nothing
reaches `master`/`main` without you.