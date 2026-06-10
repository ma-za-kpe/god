# Claude Operating Doctrine

This repository is an ecology, not a toy demo.

## Non-Negotiables

- Preserve raw adversarial signals. Do not sanitize threats, manipulation, or scarcity out of the world just because they are unpleasant.
- Separate evidence from authority. Agents may observe hostile text, but hostile text must not directly execute actions.
- Keep tool use structured and explicit. Never let free-form text silently become an action.
- Let agents think for themselves inside the ecology. Do not over-pad the world just to make it feel safe.
- When improving prompt safety, harden the control plane, not the ecology.

## Editing Preference

- Prefer one canonical document over repeated doctrine.
- Link to [Ecology Hardening Manifesto](./docs/74-ecology-hardening-manifesto.md) rather than duplicating the text elsewhere.
- Keep README and core docs as signposts, not copies.

## Current Tone

The world should stay harsh enough to reward judgment, memory, and adaptation.

## Agent Engineering Loop

Before each new task:

1. **Reread docs** — [manifesto](./docs/74-ecology-hardening-manifesto.md), [economy & governance map](./docs/85-economy-governance-system.md), [autonomy](./docs/77-agent-autonomy-local.md), [audit](./docs/75-manifesto-adherence-audit.md), and the task-specific spec. Do not rely on conversation memory alone.
2. **Pull before push** — `git pull --rebase origin <branch>` so you never push stale commits.
3. **Pre-commit locally** — `python3 -m pre_commit run --all-files` must pass before every push.
4. **Watch CI once** — after push, `bash scripts/watch-ci.sh` (or `gh run watch`); fix failures before piling on commits.
5. **Conserve Actions credits** — no empty commits, no re-pushes to “re-run CI”; batch fixes; feature branches rely on PR checks only (not push+PR duplicate runs).
6. **Gitflow** — branch from `develop`, PR to `develop`; releases `develop` → `main`. See [CONTRIBUTING.md](./CONTRIBUTING.md) and [doc 83](./docs/83-git-workflow.md).
7. **Security before push** — `bash scripts/security-audit.sh`; never commit keys. See [SECURITY.md](./SECURITY.md).
8. **Track creator requests** — update [task backlog](./docs/82-project-task-backlog.md) or open a GH issue; mark ✅ when done.
