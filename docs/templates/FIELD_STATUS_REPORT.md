# Field Status Report

> Copy to `field-reports/<github-user>-<YYYYMMDD>.md`, fill in, commit on `field/<user>/handoff-<date>`.

---

## Identity

| Field | Value |
|-------|-------|
| GitHub user | |
| Date (UTC) | |
| Machine OS | e.g. Windows 11 + WSL2 / macOS / Linux |
| RAM total / free | |
| GPU | e.g. RTX 4060 8 GB / none |

---

## Where is the project on your side?

| Question | Your answer |
|----------|-------------|
| Repo path on disk | e.g. `C:\Users\…\god` |
| Current branch | `git branch --show-current` |
| Current SHA | `git rev-parse --short HEAD` |
| Last pull from origin? | date + branch |
| Uncommitted local changes? | `git status --short` (paste output) |
| Fork or upstream clone? | `git remote -v` |

---

## What happened?

Describe in plain language (2–5 sentences):

- Did the stack ever run successfully on this machine?
- What symptom: crash, freeze, OOM, observer lag, hallucinations, never started?
- When did it last work (if ever)?
- What were you doing right before it failed (seed count, test id, browser tabs open)?

---

## Stack snapshot (paste command output)

### Git

```text
(paste: git status && git log -1 --oneline && git remote -v)
```

### Docker

```text
(paste: docker compose ps)
```

### Health

```text
(paste: curl -s http://localhost:8888/health || echo FAIL)
(paste: curl -s -o /dev/null -w '%{http_code}' http://localhost:3000 || echo FAIL)
```

### Agents (if runtime up)

```text
(paste: curl -s 'http://localhost:8888/agents?limit=5' | head -c 2000)
(paste: curl -s http://localhost:8888/stats)
```

### Host memory / Ollama

```text
(paste: Task Manager summary OR free -h)
(paste: ollama ps  OR  note if Ollama not installed)
```

### Runtime logs (required)

```text
(paste: docker compose logs runtime --tail 150)
(paste: docker compose logs postgres --tail 30 2>/dev/null)
(paste: grep -i 'error\|warn\|killed\|oom' from runtime logs — or note none)
```

---

## Environment (no secrets)

| Variable | Set? (yes/no) | Notes |
|----------|---------------|-------|
| `.env.local` exists | | do not paste contents |
| `LLM_PROVIDER` | | ollama / stub / other |
| `LLM_MODEL` | | |
| `swarm.key` present locally | | yes/no only |
| Agent count living | | from /stats or /agents |

---

## What you need from us

- [ ] Help interpreting logs
- [ ] Branch to track (develop vs feat/…)
- [ ] Lower memory profile / stub LLM guidance
- [ ] Access / swarm.key out-of-band
- [ ] Other: ___

---

## Attestation

- [ ] I did **not** commit `.env.local`, keys, wallet JSON, or bulk agent dumps
- [ ] I ran `python3 -m pre_commit run --all-files` before push
- [ ] I will comment `[FIELD-HANDOFF]` on the onboarding PR with branch @ sha
