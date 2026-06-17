# Banter Legendary Upgrade — Requirements

## Verdict

**4/10. The pipeline lives. The theater doesn't.**

The current design gets to "consistently good, occasionally very good" broadcast banter.
It will feel polished, varied, and professional.
It will NOT consistently produce the "holy shit, did that just happen?" moments that make viewers emotionally invested for months, clip like crazy, or feel like they're witnessing living cosmic beings.

The gap: **the specs are excellent at controlling output. Legendary banter requires orchestrating the conditions for uncontrolled truth while still protecting the broadcast from total derailment.** We're building a very sophisticated cage for the Elders. The goal requires opening the cage door at the right moments and trusting the archetypes enough to let them bite.

---

## Live System Findings (from runtime monitoring)

These are bugs and failures observed in the running container, not design-level gaps:

### LF-1: Arc theme name bleeding verbatim into dialogue (CRITICAL)
Elders literally say "The Market Is a Cruel Teacher But Is It Fair?" as words in their lines. The arc theme title string is being injected into the prompt and the model quotes it literally instead of thematically. Appears 6+ times per session. Completely shatters immersion. A viewer hears this once and the illusion dies.

### LF-2: No actual conversation — disconnected one-liners
Zero evidence any Elder is genuinely responding to what the previous Elder said. Each line is generated in near-isolation. Forge says "You claimed authority earlier On what basis?" and Weave's next line is "The records show a pattern Shall I read it aloud?" — these don't connect. No escalation arc, nothing building. Viewers watching two exchanges in a row will notice immediately.

### LF-3: Archetype voices are indistinguishable
Shade (parasite), Store (hoarder), Forge (builder) all sound like the same generic debater. The Parasite isn't extracting value. The Hoarder isn't defending scarcity like doctrine. "Sit down. The grown-ups are talking." (hoarder) and "Boring New game Who is in?" (cooperator) — no archetype fingerprint on either.

### LF-4: Subjectless third-person lines — inconsistent register
Lines like "confuses volume for authority", "talks like someone who has never lost anything", "is still reading last week's headlines" — these are editorial commentary, not speech. Either a valid rhetorical device or broken generation; no consistency.

### LF-5: Cross-Elder repetition not caught
"Some wounds are not for public display" from two different Elders. "Useful framing Still dodges the cost" twice from Shade. Anti-repetition catches per-Elder ngrams but not cross-Elder or multi-session gaps.

### LF-6: Grammar breakage
"You claimed authority earlier On what basis?" — missing period. Lines lack sentence boundaries. "Chaos mode Buckle up, everybody" and "Breaking news: you are behind." break the Elder register entirely — they sound like Discord mods and sports tickers.

### LF-7: No emotional vulnerability in output
Out of 60 lines sampled, 2–3 showed genuine vulnerability ("Must be nice Having no scars", "I have bled for less convincing arguments"). Everything else is performative attack or deflection. No Elder sounds genuinely hurt, doubting, or broken before snapping back.

### LF-8: Meta/audience awareness entirely absent
No Elder acknowledges the Veil, the Swarm, patron power, or being watched. The "GOD Touch" per the target standard is completely missing from output.

---

## Design-Level Gaps (the philosophical critique)

### DG-1: Sharp Character-Driven Wit — partially covered but fragile
VoiceDNA + anti-patterns + move selector are good attempts. But forcing "transactional sentence structures" or "clipped dismissive rhythm" via prompts often produces stiff, uncanny cosplay rather than organic character voice. Real legendary banter feels like the character is thinking and bleeding their worldview in real time, not applying a linguistic fingerprint checklist.

**What's needed:** Archetypes need a few deeply-held *beliefs* and *fears* baked into their system prompt, not just linguistic patterns. A Parasite should be terrified of being seen as weak; a Hoarder should believe every shared resource is a future deprivation. These beliefs generate voice naturally.

### DG-2: Unpredictability + Emergent Surprise — weakest area
The system has heavy orchestration: Move_Selector probabilities, Scene_Context, tension decay, anti-repetition gates, quality gates with refinement loops. This fights true emergence. The best AI banter moments come from the model being allowed to go off the rails in character-consistent ways. The current design is too afraid of bad output, which kills the chaos that makes people clip things.

**What's needed:** Intentional "chaos windows" — at tension >8 or mid-session peaks, relax quality gating significantly, disable anti-repetition for one turn, let one unexpected move break the pattern. Also: cross-pair eavesdropping (Elder-A hears Elder-B's conversation with Elder-C and reacts) creates genuine surprise.

### DG-3: Emotional Texture & Vulnerability — surface-level only
Emotional_Primer and Relationship_Memory are steps in the right direction, but turning history into "visceral present-tense statements" is still *telling*, not *showing*. Real vulnerability hits when an Elder momentarily drops their archetype mask, contradicts their core drive, or sounds genuinely hurt/broken for one beat before snapping back. The specs mostly keep everything in archetype lanes.

**What's needed:** Explicit "vulnerability triggers" — a move type or scene condition that allows and rewards a single line of mask-drop. E.g., when tension > 9 and the pair has a betrayal record, a 20% chance the responding Elder's line must *not* be their archetype's default defense — it must expose a crack. This cannot be a prompted instruction alone; the model needs permission to be wrong for one turn.

### DG-4: Rhythm & Musicality — mechanically addressed, artistically missing
PacingController is decent (delays based on scores, heated vs cooling). But true conversational music includes natural interruptions, overlapping, trailing off, vocal texture changes, backchannels, and pregnant silences that feel earned. The system is still mostly "generate line → wait X seconds → next."

**What's needed:** Backchannel lines (very short, reactive: "Ridiculous.", "Still going?", "..."), overlapping triggers when tension is peak, and deliberate silence beats (no line generated for 2–3 seconds). The dialogue engine needs to model conversation *flow*, not just individual turn quality.

### DG-5: Thematic Depth Tied to World — mentioned but not enforced deeply
Arc_Theme exists but nothing forces Elders to tie petty arguments back to ma-za-kpe ecology, divine patronage, or cosmic costs in a way that feels profound instead of tacked-on. The arc theme is currently injected as a title string, which the model repeats verbatim (see LF-1).

**What's needed:** Arc themes must be injected as directives with world-context, not titles. "The current arc is about scarcity as cosmic punishment — every line should feel like hoarding or spending is an act of devotion or heresy." This requires a thematic context builder separate from the theme name.

### DG-6: Shareability — adequate but engineered wrong
Callback_Registry and Subtlety_Director help. But quotable lines emerge from raw truth + surprise, not from engineered shareability bonuses. The current spec adds a +1 to shareability when subtext is injected — this rewards mechanical conformance, not genuine impact.

**What's needed:** Stop trying to score shareability. Make the lines more dangerous and true and the clips will emerge organically. The constraint should be "does this line reveal something true about this character's deepest conflict?" not "does this line have loaded subtext?"

### DG-7: Self-Awareness & Meta Layer — barely present
Mentioned in the goal, almost absent from the requirements. The "GOD Touch" (acknowledging the Swarm, patronage as real power, performing for gods) is one of the highest-leverage differentiators from any other AI chatbot system. It's what makes the ecology feel alive in a way no other system can replicate. Currently not enforced in any prompt anywhere.

**What's needed:** A `VeilLayer` module that injects Swarm awareness into 1-in-8 lines. The Elder knows they are performing. They know patrons are wagering on their words. They know silence costs rent. This does not break immersion — it *is* the immersion for the GOD world.

---

## The Philosophical Shift Required

> The current specs optimize for reliability, variety, and controlled quality.
> The target demands dangerous aliveness, emotional risk, and emergent truth.

**Do you want safe, high-floor banter, or do you want the risky, high-ceiling, rewatchable legendary shit?**

The current docs lean heavily toward the former.

This isn't a small tweak. It's a philosophical shift from "make reliable character dialogue" to "create conditions where characters can surprise even us."
