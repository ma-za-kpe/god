# Commands

Avatar lab prime directive: see [AGENTS.md](./AGENTS.md). The local avatar goal
is continuous LLM-directed browser video; hard-coded avatar behavior is only an
explicit test fallback, never the product path.

Local browser avatar lab:

```powershell
.\scripts\start-local-avatar-lab.ps1 -OpenBrowser
```

Dry run without starting Docker:

```powershell
.\scripts\start-local-avatar-lab.ps1 -DryRun
```

Single command to bring the Vast stack up and wait for everything required by `/stage`:

```bash
bash /workspace/god/scripts/vast-restart-services.sh
```

Public `/stage` URL:

```text
http://ssh7.vast.ai:10517/stage
```

The launcher blocks until PostgreSQL, Redis, NATS, IPFS, ComfyUI, fish-speech,
the observer on `:3000`, nginx, Ollama, and the runtime are all healthy.
On this host fish-speech is started in a detached `tmux` session so it survives
the SSH control shell.

Staged startup is now preferred for live recovery:

```bash
bash /workspace/god/scripts/vast-run-staged-restart.sh
```

Stage-specific recovery is also available:

```bash
bash /workspace/god/scripts/vast-restart-services.sh core
bash /workspace/god/scripts/vast-restart-services.sh voice
bash /workspace/god/scripts/vast-restart-services.sh observer
bash /workspace/god/scripts/vast-restart-services.sh streaming
bash /workspace/god/scripts/vast-restart-services.sh runtime
```

fish-speech is now a GPU-only startup contract:

```bash
FISH_DEVICE=cuda
FISH_HALF_MODE=--half
```

Sync choices:

- Git push/pull when repo permissions allow it
- Direct SSH overwrite when Git push is blocked and the host needs an immediate patch
