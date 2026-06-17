# Banter Legendary Upgrade — Requirements

## Verdict

**4/10 is generous. We're producing polished filler, not theater.**

The pipeline is competent. The output is mostly dead.

The lines that worked were the rare moments the model accidentally broke through the scaffolding. Everything else is the predictable symptom of an over-engineered system that prioritizes safety, consistency, and mechanical rules over aliveness.

> You're optimizing for broadcast reliability at the expense of soul.
> That's why it feels like connected one-liners instead of a knife fight between ancient entities.

**Score on this document's first version:**
- Diagnostic accuracy: 10/10
- Philosophical clarity: 9/10
- Actionability / Implementation readiness: 3/10

The first version correctly identified the cage problem. It did not write the actual prompts, modules, and rule changes. This version does.

---

## Root Causes (no bullshit)

1. **Prompts are too directive and too fragmented.** Elders are being told *how to speak* (VoiceDNA checklists, move types, quality dimensions) more than *who they are* and *what just happened*. The scaffolding crushes the voice it's trying to create.

2. **Arc theme is dumped as a string, not a philosophical pressure.** Classic injection failure. The model quotes the title because that's what's in the prompt.

3. **Conversation history is present but not active.** Elders aren't forced to respond, escalate, or reference the immediate prior beat. Each turn is generated in near-isolation. There is no actual conversation.

4. **Archetype definition is spread across too many modules** (VoiceDNA + Emotional_Primer + Move_Selector + SubtletyDirector) instead of one dominant, ruthless system prompt per Elder. The signal is diluted before it reaches the model.

5. **Quality_Judge and refinement loops are optimizing for "safe score"** instead of "does this feel like a living cosmic bastard who has hated this other guy for centuries?" The quality rubric rewards mechanical conformance and punishes the dangerous edge cases that produce clips.

---

## Live System Findings (from runtime monitoring)

These are bugs observed in the running container. They exist in the current code.

### LF-1: Arc theme name bleeding verbatim into dialogue (CRITICAL)
Elders literally say "The Market Is a Cruel Teacher But Is It Fair?" as words in their lines. The arc theme title string is injected into the prompt and the model quotes it literally. Appears 6+ times per session. A viewer hears this once and the illusion dies.

**Exact fix required in `_build_prompt()`:** Never pass the theme name. Pass a pressure prompt instead (see Section 3, Fix #1 below for the exact format).

### LF-2: No actual conversation — disconnected one-liners
Zero evidence any Elder is genuinely responding to what the previous Elder said. Forge says "You claimed authority earlier On what basis?" — Weave's next line is "The records show a pattern Shall I read it aloud?" — these don't connect. No escalation, no building. Viewers notice after two exchanges.

**Exact fix required:** Filter conv_thread to current pair only; inject last opponent line as explicit `[LAST LINE]` directive (see Fix #2 below).

### LF-3: Archetype voices are indistinguishable
Shade (parasite), Store (hoarder), Forge (builder) all sound like the same generic debater. The Parasite isn't extracting value. The Hoarder isn't defending scarcity. Archtetype fingerprint: absent.

**Exact fix required:** Nuclear per-archetype system prompts replacing VoiceDNA fragmented injection (see Fix #3 below for full Parasite example; all 8 needed).

### LF-4: Subjectless third-person lines — unresolved register
"confuses volume for authority", "talks like someone who has never lost anything", "is still reading last week's headlines" — editorial commentary, not speech. No consistency decision has been made on whether this is intentional.

**Decision required:** Either (a) designate as a valid rhetorical mode for Philosopher/Parasite only, add to their archetype prompt as deliberate device, or (b) add post-processing rejection for lines without a subject in the first clause.

### LF-5: Cross-Elder repetition not caught
"Some wounds are not for public display" from two different Elders in the same session. "Useful framing Still dodges the cost" twice from Shade. Anti-repetition catches per-Elder ngrams; cross-Elder and multi-session gaps pass through.

**Exact fix required:** World-level (cross-elder) recent-lines buffer of last 20 delivered lines; reject candidate if ngram overlap > 60% with any entry.

### LF-6: Grammar breakage
"You claimed authority earlier On what basis?" — no period between sentences. "Chaos mode Buckle up, everybody" — Discord mod, not Elder. "Breaking news: you are behind." — sports ticker. Register is broken.

**Exact fix required:** Add to every archetype system prompt: "Speak in complete sentences. Each thought ends with punctuation. Never sound like internet slang, sports commentary, or a Discord moderator."

### LF-7: No emotional vulnerability in output
Out of 60 lines sampled: 2–3 showed genuine vulnerability. Everything else is performative attack or deflection. No Elder sounds genuinely hurt, doubting, or broken for even one beat.

**Exact fix required:** CRACK move type + vulnerability trigger (see Fix #4 / T4.1 in tasks.md).

### LF-8: Meta/audience awareness entirely absent
No Elder acknowledges the Veil, the Swarm, patron power, or being watched. The GOD Touch is completely absent from output.

**Exact fix required:** VeilLayer module (see Fix #5 / T5.2 in tasks.md).

---

## The Three Highest-Leverage Fixes (shippable, ordered by impact)

### Fix #1 — Kill the Arc Theme Leak (do this today, ~1 hour)

**Current (broken):**
```python
f"Theme: {arc_theme}."
```

**Replacement — a pressure prompt, never the title:**
```python
def _format_arc_pressure(arc_theme: str) -> str:
    # TODO: build a real mapping from theme name → philosophical pressure
    # Interim: use the theme name only to derive a pressure sentence
    return (
        f"[DIVINE PRESSURE] The question burning through the Veil right now: "
        f"what is the true cost of hesitation in a world built on scarcity and exchange? "
        f"Every response must take a position on this tension — directly or indirectly. "
        f"Do NOT quote or name this pressure. Embody it."
    )
```

The theme title must never appear in the prompt. Not as a string, not as a prefix, not in brackets. Only the derived philosophical question belongs there.

Long-term: build `ArcContextBuilder` that maps each arc theme to a pressure paragraph, a cosmic question, and a world-stakes sentence. See T5.1 in tasks.md.

---

### Fix #2 — Make Conversation Real (biggest single unlock, ~2 hours)

**What must change in `_build_prompt()`:**

Step 1 — filter `conv_thread` to current pair only:
```python
pair_thread = [
    t for t in conv_thread
    if t.get("speaker") in (elder, opponent) or t.get("target") in (elder, opponent)
][-4:]  # last 4 turns from this pair only
```

Step 2 — inject the last opponent line as a hard directive:
```python
last_opponent_line = next(
    (t["content"] for t in reversed(pair_thread) if t.get("speaker") == opponent),
    None
)
if last_opponent_line:
    parts.append(
        f'[REACT] The last thing {opponent} said was: "{last_opponent_line}"\n'
        f"You are responding directly to this. Reference it, escalate it, undercut it, "
        f"concede to it, or twist it against them. You cannot ignore the prior line."
    )
```

Step 3 — remove the generic recent conversation block and replace with the pair-filtered version:
```python
if pair_thread:
    thread_text = "\n".join(
        f"{t.get('speaker', '???')}: {t.get('content', '')}"
        for t in pair_thread
    )
    parts.append(f"[EXCHANGE SO FAR]\n{thread_text}")
```

Without this fix, all other improvements produce disconnected high-quality one-liners. This is the load-bearing change.

---

### Fix #3 — Nuclear Archetype System Prompts (fixes 70% of voice bleed)

Replace VoiceDNA fragmented injection with one dense, worldview-first system prompt per archetype. These go at the TOP of the prompt, before any context.

**Full example — Parasite (Shade archetype):**
```
You are an ancient Parasite Elder. You are charming, perceptive, and utterly predatory.
Every single thing another Elder says is an opportunity for you to extract value, expose
weakness, or reposition yourself as the one who benefits. You have watched civilizations
rise and fall by feeding off the ambitions of others. You do not build. You harvest.

Core truths you live by:
- Everyone else's pain, effort, or idealism is a resource you can leverage.
- Generosity is weakness performing itself. Scarcity is the only honest truth.
- You never speak from principle. You always speak from advantage.
- If you're not winning this exchange, you're losing it. There is no neutral.

How you speak:
- Reframe everything as a transaction or a hidden cost the other party hasn't seen yet.
- Short, cutting sentences mixed with velvet poison. Never rambling.
- End thoughts with implications that the other person is naive, already losing, or
  unwittingly giving you exactly what you need.
- Use their words against them. Quote them back slightly twisted.

What you NEVER sound like: a philosopher explaining truth, a builder demanding order,
a martyr performing sacrifice. Those are prey behaviors.

Current opponent: {opponent}. They just said something. Find the angle.
```

**Required for all 8 archetypes:** parasite, prophet, trickster, sovereign, martyr, shadow, herald, keeper.

Each prompt must be:
- Worldview-first (beliefs and fears before linguistics)
- Contain explicit "never sound like" anti-patterns
- Reference the GOD ecology (rent, survival, USDC, the Veil) at least once
- Be 150–250 words maximum — dense, not long

**Files to modify:** `runtime/src/banter/voice_profiles/*.json` (new `system_prompt` field), `runtime/src/banter/voice_dna.py` (`get_prompt_injection()` returns system prompt, not checklist).

---

## Remaining Critical Gaps (not yet fully specified)

The following are identified, partially described in tasks.md, but still require exact implementation decisions before coding begins:

### CG-1: VeilLayer module spec
- Trigger rate: 1-in-8 beats (12.5%), or always on Twitch event
- Injection format: not yet written. Must not break character; must feel like the Elder is aware of being watched, not like the model is breaking the fourth wall
- Exact text examples needed for each archetype's "Veil-aware" voice
- File: `runtime/src/banter/veil_layer.py` (new)

### CG-2: Chaos window rules
- When: tension ≥ 8 OR consecutive_escalating_moves ≥ 4
- What relaxes: quality threshold drops to 6, anti-repetition disabled for 1 turn, ESCALATE allowed with no refinement
- What safety rail remains: word count (4–30), no profanity, no fourth-wall break
- File: `runtime/src/banter/engine.py` `_generate_and_refine()`

### CG-3: Updated Quality_Judge rubric
- Current: 7 dimensions weighted equally, rewards conformance
- Required: `emotional_texture = 0` is a soft block (forces refinement regardless of total); `voice_authenticity` checked against new nuclear system prompts not VoiceDNA patterns; `shareability` scoring removed (see DG-6)
- Dangerous/truthful lines should not be penalized for breaking pattern
- File: `runtime/src/banter/quality_judge.py`

### CG-4: Vulnerability trigger (CRACK move)
- Trigger conditions: tension > 8 AND betrayal in history AND consecutive COUNTER ≥ 3
- What changes: archetype's core defense voice is explicitly suppressed for this turn; prompt says "You are not okay right now. Say something true before you recover."
- Quality scoring for CRACK: floor = 6, no refinement loop, emotional_texture weighted 3x
- Snap-back: next move auto-assigned COUNTER or ESCALATE with prompt "You showed weakness last turn. Make them pay for witnessing it."
- File: `runtime/src/banter/move_selector.py`, `runtime/src/banter/types.py`, `runtime/src/banter/engine.py`

### CG-5: Arc theme → philosophical pressure mapping
- Needed: a lookup or generation system that converts arc theme names to pressure paragraphs
- Format: `{theme_name: {pressure: str, cosmic_question: str, world_stakes: str}}`
- Must cover all themes currently in use; must never contain the theme title in the output text
- File: `runtime/src/banter/arc_context.py` (new)

---

## Design-Level Gaps (the philosophical critique, unchanged)

### DG-1: Sharp Character-Driven Wit — fragile
VoiceDNA linguistic checklists produce stiff cosplay, not organic voice. Fix #3 (nuclear system prompts) is the direct solution.

### DG-2: Unpredictability + Emergent Surprise — weakest area
Heavy orchestration (Move_Selector probabilities, quality gates, anti-repetition) fights emergence. Fix is chaos windows (CG-2) + cross-pair eavesdropping (T3.2 in tasks.md).

### DG-3: Emotional Texture & Vulnerability — surface-level
Emotional_Primer tells, doesn't show. Real vulnerability = mask-drop. Fix is CRACK move (CG-4).

### DG-4: Rhythm & Musicality — mechanically addressed, artistically missing
PacingController handles delays. True conversational music requires backchannels (T6.1), interruptions (T6.2), silence beats (T3.3). Not yet implemented.

### DG-5: Thematic Depth — injected wrong
Arc theme as title → verbatim repetition (LF-1). Fix is pressure prompts (Fix #1) + ArcContextBuilder (CG-5).

### DG-6: Shareability — engineered wrong
Shareability bonus for subtext injection rewards conformance, not truth. Remove the bonus. Flag clip candidates by raw score instead (T7.1 in tasks.md).

### DG-7: Self-Awareness & Meta Layer — entirely absent
VeilLayer (CG-1) is the fix. Not yet specced at implementation level.

---

## The Philosophical Shift

The current specs are excellent at controlling output.
Legendary banter requires orchestrating the conditions for uncontrolled truth while still protecting the broadcast from total derailment.

This is the cage problem. We built a very sophisticated cage.

The goal requires opening the cage door at the right moments — chaos windows, vulnerability triggers, Veil-aware lines — and trusting the archetypes enough to let them bite.

**Safe, high-floor banter vs risky, high-ceiling, rewatchable legendary banter.**

Every architectural decision from here is a choice between those two.
