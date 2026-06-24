# Commands

Single command to bring the Vast stack up and wait for everything required by `/stage`:

```bash
bash /workspace/god/scripts/vast-restart-services.sh
```

Public `/stage` URL:

```text
http://ssh7.vast.ai:10517/stage
```

The launcher blocks until PostgreSQL, Redis, NATS, IPFS, Ollama, ComfyUI,
fish-speech, the observer on `:3000`, nginx, and the runtime are all healthy.
