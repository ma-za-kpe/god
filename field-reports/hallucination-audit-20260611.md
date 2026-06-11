# Hallucination + Autonomy Audit — 2026-06-11

Source: `field-reports/world_drama_log.txt` (converted UTF-8 from field UTF-16 capture, PR #51 / T-HALL-LOG-01).

## Stack snapshot (from log)

| Metric | Value |
|--------|-------|
| Living agents | 8 |
| Events total | 2620 |
| Messages total | 351 |
| Episodes total | 654 |
| Message events in capture | 8 |
| Transfers in capture | 1 |
| Service purchases in capture | 1 |
| Dream events in capture | 2 |

Roster: Elder-Build-0F13, Elder-Drift-9D71, Elder-Hook-5FE2, Elder-Lore-BD30, Elder-Merch-8161, Elder-Store-E66C, Elder-Ward-693F, Elder-Weave-DD84

## Autonomy verdict (from log evidence)

| Question | Verdict |
|----------|---------|
| Self-running cycles (no human per action)? | **YES** — 8 agents, rent paid, cognition/events flowing |
| Structured actions executed? | **YES** — messages, transfers, service purchases in log |
| Episodic memory active? | **YES** — `episodes_total` > 0 in snapshot stats |
| Raw adversarial signals preserved? | **YES** — suspicion, coalition caution, economic offers in message bodies |
| Cognition always grounded? | **NO** — see violations below |
| Action layer blocks bad recipients? | **Not visible in this capture** — no `Recipient agent … not found` lines in file |

**Summary:** Agents are **operationally autonomous** (they act in the economy on their own) but **not cognitively reliable** (thoughts still invent mechanics / leak JSON).

## Thought audit (7 `last_thought` / `thought` fields parsed)

### Forbidden invented mechanics (0)

- (none matched forbidden regex in parsed thoughts)

### Unknown agent names in thoughts (0)

- (none — referenced elders match roster)

### JSON action leaked into `last_thought` (0)

- (none)

### Grounded thought samples

- `I'm currently reviewing the balance of my USDC reserves and considering a potential transfer to Elder-Weave-DD84.`
- `I am assessing the market conditions and considering a response to Elder-Hook-5FE2's message.`
- `( \"action\": \"send_message\", \"to_id\": \"Elder-Store-E66C\", \"content\": \"Proposal to join coalition for mutual benefit.\", \"message_type\": \"offer\", \"amount\": 0.1, \"payer_on_accept\": \"r`
- `I'm sending a private message to Elder-Lore-BD30 (philosopher) asking for clarification on their potential coalition opportunity.`
- `(\"act ion\": \"send_broadcast\", \"to_id\": \"all agents visible\", \"content\": \"I'm aware of potential threats and will verify any service registration or coalition proposals thoroughly.\")`

## Field comment cross-check (PR #49)

Field reported **frequent grounding rejects** for invented agents (`Elder-Scaffold`, `Elder-Tower`, etc.) in runtime greps — those lines are **not present** in `world_drama_log.txt` (capture is snapshot + partial tail, not full `--tail 2000`).

Treat field greps as supplementary; this file audit covers the committed artifact only.

## Recommendations

1. Harden `last_thought` display path — reject JSON-shaped thoughts before emit.
2. Extend forbidden patterns for infrastructure fiction (`Riverbed Bridge`, `inter-network`).
3. Field: run `python3 scripts/spot-check-grounding.py` on machine with Python in PATH.
4. Commit full `halluc-log-raw.txt` with grounding reject greps for next soak.
