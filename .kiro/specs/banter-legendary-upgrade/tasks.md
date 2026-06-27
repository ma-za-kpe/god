# Banter Legendary Upgrade — Task List

Current rating: **4/10** against the legendary standard.
Target: dangerous aliveness, emotional risk, emergent truth, clip-worthy moments.

See `requirements.md` for full critique and rationale behind each item.

---

## TIER 1 — Critical Bugs (breaks immersion now, fix first)

- [ ] **T1.1 Fix arc theme name leaking verbatim into dialogue**
  - Root cause: arc_theme title string injected directly into prompt; model quotes it literally
  - Fix: replace theme injection with a thematic directive: "The current arc explores [theme concept] — [1-sentence world-context]. Do NOT quote this phrase; embody the tension."
  - Files: `runtime/src/banter/engine.py` `_build_prompt()`, `runtime/src/archetype_graphs.py`
  - Success: no line should ever contain the literal arc theme title string

- [ ] **T1.2 Make Elders actually respond to each other (conversation not monologue)**
  - Root cause: conv_thread passed but not filtered by pair; each Elder sees a mix of unrelated conversations from other pairs
  - Fix: filter conv_thread to only include turns from the specific elder↔opponent pair; ensure last 4 turns from THIS pair are in context
  - Files: `runtime/src/banter/engine.py` `generate_beat()`, `_build_prompt()`
  - Success: Forge's line should visibly react to what Weave just said

- [ ] **T1.3 Fix grammar — enforce sentence boundaries in generation**
  - Root cause: model generates run-on lines without punctuation between clauses
  - Fix: add post-processing to split on unambiguous clause boundaries, or add instruction "Each line must be a complete, grammatically correct sentence or 2–3 short complete sentences." to prompt
  - Success: no more "You claimed authority earlier On what basis?" — should be "You claimed authority earlier. On what basis?"

- [ ] **T1.4 Cross-Elder and session repetition detection**
  - Root cause: anti-repetition only checks per-elder ngrams within a session
  - Fix: add a world-level (cross-elder) recent-lines buffer (last 20 lines from any elder); reject if ngram overlap > 60%
  - Files: `runtime/src/banter/anti_repetition.py`
  - Success: "Some wounds are not for public display" cannot appear from two different Elders in the same session

---

## TIER 2 — Voice & Archetype Differentiation

- [ ] **T2.1 Replace VoiceDNA linguistic checklists with belief + fear prompts**
  - Each Elder archetype gets 2 core beliefs and 1 core fear injected as directives, not as linguistic patterns
  - Example (Parasite): "Core belief: every exchange is extractive; nothing is freely given. Core belief: strength is the only honest currency. Core fear: being seen as weak or needy. Every line must reflect one of these."
  - Example (Hoarder): "Core belief: every resource shared today is a deprivation survived tomorrow. Core fear: the vault running empty. Let scarcity bleed into every word."
  - Files: `runtime/src/banter/voice_profiles/*.json` (new `beliefs` and `fear` fields), `runtime/src/banter/voice_dna.py`

- [ ] **T2.2 Make subjectless third-person lines consistent or remove**
  - Decide: are "confuses volume for authority" style lines intentional Elder rhetorical mode or a bug?
  - If intentional: add to VoiceDNA as valid "commentary mode" for specific archetypes (Philosopher, Parasite); enforce consistency
  - If bug: add post-processing to reject lines without a subject in the first clause

- [ ] **T2.3 Archetype-specific forbidden moves**
  - A Hoarder should never CONCEDE without heavy cost. A Parasite should never DEFEND without pivoting to extraction. A Martyr should rarely DEFLECT.
  - Add per-archetype move exclusions or heavy weight penalties to move_selector
  - Files: `runtime/src/banter/move_selector.py`

---

## TIER 3 — Emergence & Unpredictability

- [ ] **T3.1 Chaos windows — loosen quality gating at peak tension**
  - When tension ≥ 8 OR consecutive escalating moves ≥ 4: lower quality pass threshold to 6 (from 10), disable anti-repetition for 1 turn, allow ESCALATE with no refinement loop
  - The chaos window should feel like the cage door opened for exactly one beat
  - Files: `runtime/src/banter/engine.py` `_generate_and_refine()`

- [ ] **T3.2 Cross-pair eavesdropping events**
  - 1-in-10 beats: inject the last line from a *different* ongoing pair into the current Elder's context as "overheard: [Elder-X to Elder-Y]: '[line]'"
  - This creates genuine lateral surprise — Elder-A reacting to Elder-B's argument with Elder-C
  - Files: `runtime/src/banter/engine.py` `_build_prompt()`, `runtime/src/scene_context.py`

- [ ] **T3.3 Intentional silence beats**
  - When tension is decreasing (≤ 3) or after a high-score line (> 14), 15% chance of a "silence beat" — no line generated, pacing adds 3–5 seconds, overlay shows "..." or the Elder's name with no speech
  - This is the "pregnant pause" that makes the next line land harder

---

## TIER 4 — Emotional Depth & Vulnerability

- [ ] **T4.1 Vulnerability triggers — mask-drop moments**
  - New move type: `CRACK` — triggered when: tension > 8 AND betrayal in history AND consecutive COUNTER ≥ 3
  - CRACK move: the Elder's line must NOT use their archetype's default defense voice. Must reveal doubt, exhaustion, or a moment of honesty before snapping back next turn.
  - Quality judging for CRACK lines should reward rawness, not polish — lower threshold (6), score "emotional_texture" weighted 3x
  - Files: `runtime/src/banter/move_selector.py`, `runtime/src/banter/types.py`, prompts

- [ ] **T4.2 Post-vulnerability snap-back (2-turn emotional arc)**
  - After a CRACK beat, the Elder's next move is automatically COUNTER or ESCALATE with a note in the prompt: "You showed weakness last turn. Recover. Make them pay for witnessing it."
  - This creates the "drops mask → snaps back harder" rhythm that drives emotional investment

- [ ] **T4.3 Alliance moments — temporary vulnerability via trust**
  - When alliance flag is set in RelationshipMemory: 1-in-5 chance the responding line includes a genuine agreement or compliment before pivoting to competition
  - Example: "You're not wrong about that. Which is exactly why I won't let you have it."
  - Files: `runtime/src/banter/engine.py` `_build_prompt()` (use pair_state.alliance)

---

## TIER 5 — World-Grounding & Meta Layer

- [ ] **T5.1 Arc theme thematic context builder**
  - Replace bare theme string with a 2–3 sentence world-context paragraph generated at arc start
  - Structure: "[Theme concept] in the GOD ecology means [specific world implication]. The stakes: [what patrons are watching for]. The unspoken question: [philosophical tension]."
  - This paragraph replaces the theme title in all prompts
  - Files: `runtime/src/showrunner.py`, new `runtime/src/banter/arc_context.py`

- [ ] **T5.2 VeilLayer — meta-awareness injection**
  - New soul module: `VeilLayer`
  - Activates on 1-in-8 beats (12.5% rate), or always when audience reaction event fires
  - Injects: "The Swarm watches. Your patron's wager rides on this exchange. Acknowledge the audience — not by breaking character, but by performing *for* them."
  - Generates lines where the Elder is aware of stakes beyond the personal argument
  - Example output: "The Swarm will remember this. Choose carefully." / "Even the patron gods are silent right now. Good."
  - Files: new `runtime/src/banter/veil_layer.py`, wire into `engine.py` `_build_soul_prompt()`

- [ ] **T5.3 Patronage-cost grounding**
  - 1-in-5 lines should reference the economic reality of the GOD world: rent, USDC balances, death, survival
  - Not as exposition — as lived stakes: "My rent is due because of what you just said." / "That argument costs more than your balance can afford."
  - Files: snapshot USDC balance for the two Elders into `_build_prompt()` context

- [ ] **T5.4 World-event reactions**
  - When a world-first or milestone fires, inject it into the next 3 banter beats: "Something just changed in the ledger. Everyone felt it."
  - Makes the world feel live and reactive, not canned
  - Files: `runtime/src/banter/engine.py`, `runtime/src/world_snapshot.py`

---

## TIER 6 — Rhythm & Flow

- [ ] **T6.1 Backchannel lines**
  - New line type: 1–4 word reactive utterance with no move scoring, no quality gating
  - Examples: "Ridiculous.", "Still going?", "...of course.", "Bold claim.", "Careful."
  - Triggered: when opponent's previous line scored > 12 (landed hit) or scored < 5 (weak attempt)
  - Inserted BETWEEN the normal generation pipeline, takes 0.5s delay
  - Files: new `runtime/src/banter/backchannel.py`

- [ ] **T6.2 Interruption mechanic**
  - At tension > 8: 20% chance the responding Elder's line starts with "—" (em-dash interrupt) and references the opponent's previous line mid-sentence
  - Example: "—because that is exactly the lie you've told every patron who trusted you."
  - This breaks the perfect-turn structure and creates conversational feel
  - Files: `runtime/src/banter/engine.py`, PacingController

- [ ] **T6.3 Trailing-off and incomplete lines**
  - At CONCEDE or DEFLECT moves with low tension (≤ 3): allow lines that trail: "Maybe. But... no."  / "I was going to say something important. I changed my mind."
  - These feel like hesitation, which creates emotional texture cheaply

---

## TIER 7 — Quality System Recalibration

- [ ] **T7.1 Stop scoring shareability mechanically**
  - Remove the subtext_depth shareability bonus (currently engineered as +1 per subtext injected)
  - Replace with: flag a line as "clip candidate" if: total > 16 AND sharpness = 3 AND emotional_texture ≥ 2
  - Track clip candidates in BeatResult.metadata for the broadcaster overlay
  - Files: `runtime/src/banter/quality_judge.py`

- [ ] **T7.2 Weight emotional_texture 2x in refinement threshold**
  - Current 7-dimension scoring weights all dims equally
  - Refinement feedback should call out emotional_texture = 0 as a hard block: "This line has no emotional texture. It must feel like something. Rewrite."
  - Files: `runtime/src/banter/quality_judge.py` `EnhancedQualityScore.refinement_feedback()`

- [ ] **T7.3 Per-move quality floor differentiation**
  - CRACK moves: floor = 6, no refinement loop (raw is the point)
  - ESCALATE at tension > 8: floor = 8 (still needs to land)
  - CONCEDE: floor = 5 (graceful collapse is fine at lower scores)
  - CALLBACK: floor = 10 (it must earn the reference)
  - Files: `runtime/src/banter/engine.py`

---

## TIER 8 — Tracking & Measurement

- [ ] **T8.1 Clip candidate overlay**
  - When a line is flagged as clip candidate, show a visual marker in the Twitch overlay (star, glow, etc.)
  - Log clip candidates to DB for session review

- [ ] **T8.2 Archetype voice adherence metric**
  - After each session, compute per-archetype voice_authenticity distribution
  - If any archetype scores mean < 1.5 across a session, flag for prompt tuning

- [ ] **T8.3 Conversation coherence metric**
  - Track: what % of lines reference a specific word or phrase from the opponent's previous line
  - Target: > 40% of lines show explicit response to previous line (not just topic continuation)
  - Current estimate from live logs: ~10%

- [ ] **T8.4 Session emotional arc tracking**
  - Track tension curve per pair per session
  - Flag sessions where tension never exceeds 6 (too flat) or never drops below 7 (no relief)
  - Target: at least 2 distinct tension peaks and 1 valley per session

---

## Priority Order for Maximum Impact

1. T1.1 (arc theme bug) — 10 minutes, massive immersion gain
2. T1.2 (conversation coherence) — biggest quality gap from viewer perspective
3. T5.2 (VeilLayer) — unique differentiator, no other AI theater has this
4. T4.1 (vulnerability/CRACK) — drives emotional investment
5. T3.1 (chaos windows) — the "cage door" moment
6. T2.1 (belief + fear prompts) — fixes archetype indistinguishability
7. T6.1 (backchannels) — conversational feel, low cost
8. T5.1 (arc theme context builder) — deep world-grounding
9. T1.3 (grammar) — polish
10. T3.2 (cross-pair eavesdropping) — emergent surprise
