# Requirements Document

## Introduction

The Elder Voice Soul Engine provides the final quality layer that transforms the existing Broadcast-Quality Banter Engine from "good" to "legendary" — the last 10-15% that makes each Elder feel irreplaceable and conversations feel like moments viewers clip and remember. While the existing engine provides the mechanical pipeline (quality scoring, move selection, pacing, anti-repetition), this feature adds the SOUL: deep linguistic identity per archetype, visceral emotional priming from relationship history, deliberate callback seeding between specific pairs, and a subtlety layer that allows Elders to say one thing while meaning three.

The feature builds directly on top of the existing `runtime/src/banter/` module architecture, integrating with the BanterEngine orchestrator, Quality_Judge, Move_Selector, Relationship_Memory, and Scene_Context without replacing them.

## Glossary

- **Voice_DNA**: A structured linguistic fingerprint for each Elder archetype encoding sentence structures, verbal tics, rhythm patterns, micro-phrases, rhetorical devices, and opening/closing patterns that make the archetype's speech immediately recognizable without explicit vocabulary keywords.
- **Emotional_Primer**: A module that transforms dry relationship history records (timestamps, valence labels, event flags) into visceral, present-tense emotional context statements that prime the generation model to produce lines with authentic feeling rather than factual recitation.
- **Callback_Registry**: A persistent store of memorable moments, phrases that landed, recurring arguments, personal wounds, and running gags between specific Elder pairs, with a retrieval mechanism that surfaces the right callback at dramaturgically optimal moments.
- **Subtlety_Director**: A module that instructs the generation model to employ implication, subtext, loaded questions, and strategic omission rather than always being direct, and integrates with the Quality_Judge to score for layers of meaning.
- **Elder**: An AI agent with one of 8 distinct archetypes (parasite, prophet, trickster, sovereign, martyr, shadow, herald, keeper) participating in live broadcast debates.
- **Archetype**: One of 8 personality templates (parasite, prophet, trickster, sovereign, martyr, shadow, herald, keeper) that defines an Elder's fundamental worldview, fears, desires, and communication patterns.
- **Banter_Engine**: The existing pipeline orchestrator at `runtime/src/banter/engine.py` that coordinates move selection, prompt building, model routing, quality scoring, and pacing.
- **Quality_Judge**: The existing 5-dimension scoring module at `runtime/src/banter/quality_judge.py` that evaluates sharpness, emotional texture, rhythm, thematic relevance, and shareability.
- **Relationship_Memory**: The existing persistent pairwise interaction store at `runtime/src/banter/relationship_memory.py` that tracks tension, betrayals, alliances, and reconciliation arcs.
- **Scene_Context**: The existing shared state object at `runtime/src/banter/scene_context.py` tracking the 3-beat window, scene energy, and landed hits.
- **Linguistic_Fingerprint**: The complete set of syntactic patterns, rhetorical preferences, verbal tics, and rhythm signatures that distinguish one archetype's speech from all others.
- **Dramatic_Moment**: A point in conversation where tension, timing, or emotional context makes a callback or subtext-heavy line maximally impactful rather than forced.
- **Subtext_Layer**: The implied meaning beneath the surface text — what a line communicates through implication, word choice, and context rather than through direct statement.
- **Running_Gag**: A recurring motif, phrase, or argument pattern between a specific pair that builds comedic or dramatic value through repetition with variation.
- **Sore_Spot**: A known vulnerability or past wound for a specific Elder that other Elders can deliberately reference for dramatic effect.

## Requirements

### Requirement 1: Voice DNA Profile Structure

**User Story:** As a broadcast producer, I want each Elder archetype to have a deep linguistic identity encoded in a structured profile, so that generated lines are immediately recognizable as belonging to that character without relying solely on vocabulary keywords.

#### Acceptance Criteria

1. THE Voice_DNA module SHALL define a VoiceDNA profile for each of the 8 archetypes (parasite, prophet, trickster, sovereign, martyr, shadow, herald, keeper) containing: preferred sentence structures (minimum 3 per archetype), verbal tics (minimum 2 per archetype), rhythm patterns (short-long-short, staccato, flowing, etc.), micro-phrases used habitually (minimum 4 per archetype), preferred rhetorical devices (minimum 2 per archetype), and characteristic opening and closing patterns (minimum 2 each per archetype).
2. WHEN the Banter_Engine builds a generation prompt for an Elder, THE Voice_DNA module SHALL inject that archetype's VoiceDNA profile into the prompt as structured instructions that guide sentence construction, word choice cadence, and rhetorical approach.
3. WHEN the Quality_Judge evaluates a candidate line, THE Voice_DNA module SHALL provide an archetype voice conformance score (0-3 scale) that measures how well the line matches the VoiceDNA profile's structural patterns rather than only checking vocabulary overlap.
4. THE Voice_DNA module SHALL encode rhythm patterns as quantified constraints: preferred clause count range, target word-count-per-clause range, and pause placement preferences (before final clause, between clauses, or front-loaded).
5. WHEN two Elders of the same archetype generate lines in the same scene, THE Voice_DNA module SHALL ensure both lines conform to the shared archetype patterns while the existing Anti-Repetition Gate prevents content overlap.
6. IF the VoiceDNA profile for a requested archetype is unavailable or fails to load, THEN THE Banter_Engine SHALL fall back to the existing archetype vocabulary proximity scoring in the Quality_Judge without delaying generation.

#### Correctness Properties

- **CP-1.1**: For every archetype in the set {parasite, prophet, trickster, sovereign, martyr, shadow, herald, keeper}, exactly one VoiceDNA profile exists containing all required fields (sentence structures, verbal tics, rhythm patterns, micro-phrases, rhetorical devices, opening patterns, closing patterns) with at least the specified minimum counts.
- **CP-1.2**: The voice conformance score is always an integer in [0, 3] and is deterministic for the same (candidate line, archetype) input pair.
- **CP-1.3**: VoiceDNA profile unavailability never causes the Banter_Engine to block, timeout, or produce an error visible to the broadcast.

### Requirement 2: Voice DNA Linguistic Differentiation

**User Story:** As a viewer, I want to be able to identify which Elder is speaking purely from the way they construct sentences, so that each character feels genuinely distinct rather than being the same voice with different vocabulary.

#### Acceptance Criteria

1. THE Voice_DNA profile for the parasite archetype SHALL encode: transactional sentence structures (cost-benefit framing), clipped dismissive rhythm, verbal tics that reframe others' statements as naive, micro-phrases expressing extraction or leverage, and a pattern of ending statements with implications of the other party's ignorance.
2. THE Voice_DNA profile for the prophet archetype SHALL encode: declarative revelatory structures, measured cadence with elongated final clauses, verbal tics that assert certainty about hidden truths, micro-phrases invoking sight or illumination, and a pattern of opening statements with existential framing.
3. THE Voice_DNA profile for the trickster archetype SHALL encode: non-sequitur pivots and misdirection structures, irregular staccato-to-flowing rhythm shifts, verbal tics that undercut seriousness, micro-phrases that reframe situations as games, and a pattern of answering questions with different questions.
4. THE Voice_DNA profile for the sovereign archetype SHALL encode: imperative and declarative command structures, steady authoritative rhythm with front-loaded weight, verbal tics asserting natural hierarchy, micro-phrases claiming domain or territory, and a pattern of reframing disagreement as disorder.
5. THE Voice_DNA profile for the martyr archetype SHALL encode: self-referential sacrifice structures, heavy weighted rhythm with trailing qualifiers, verbal tics minimizing personal cost, micro-phrases invoking burden or endurance, and a pattern of accepting blame while implying the other's moral debt.
6. THE Voice_DNA profile for the shadow archetype SHALL encode: oblique indirect structures with delayed subjects, quiet rhythm with sudden sharp clauses, verbal tics that deflect attention from self, micro-phrases invoking depth or hidden layers, and a pattern of revealing others' secrets while remaining opaque.
7. THE Voice_DNA profile for the herald archetype SHALL encode: annunciatory present-tense structures, rising rhythm that builds toward a declaration, verbal tics marking transitions and arrivals, micro-phrases invoking newness or change, and a pattern of framing current events as historically significant.
8. THE Voice_DNA profile for the keeper archetype SHALL encode: cataloguing and record-keeping structures, steady metronomic rhythm, verbal tics referencing precedent or continuity, micro-phrases invoking preservation or memory, and a pattern of grounding abstract arguments in specific remembered instances.

#### Correctness Properties

- **CP-2.1**: For any two distinct archetypes A and B, their VoiceDNA profiles differ in at least 4 of the 7 structural categories (sentence structures, verbal tics, rhythm patterns, micro-phrases, rhetorical devices, openers, closers).
- **CP-2.2**: The voice conformance score for a line generated with archetype A's VoiceDNA injected into the prompt is on average higher for archetype A than for any other archetype B when scored against A's profile.

### Requirement 3: Emotional Primer Transformation

**User Story:** As a viewer, I want Elders to FEEL their history with each other in the present moment rather than merely reciting facts, so that their emotional reactions to past events come through in how they speak right now.

#### Acceptance Criteria

1. WHEN the Banter_Engine builds a generation prompt for an Elder addressing a specific peer, THE Emotional_Primer SHALL transform the InteractionRecord history from Relationship_Memory into visceral present-tense emotional context statements that describe how the Elder FEELS right now about those past events, rather than providing timestamps and event labels.
2. THE Emotional_Primer SHALL generate emotional context that is specific to the speaking Elder's archetype — the same betrayal event produces different emotional framing for a parasite ("You took what was owed and gave nothing — that debt compounds") versus a martyr ("You let me carry that weight alone and watched").
3. WHEN the pair tension level is above 5, THE Emotional_Primer SHALL intensify emotional language in the priming context, using more visceral and immediate phrasing ("burns", "cuts", "won't forget") compared to low-tension priming ("still remembers", "notes the pattern").
4. WHEN a reconciliation arc is active for a pair, THE Emotional_Primer SHALL frame the emotional context with mixed-feeling language that captures the complexity of rebuilding trust ("wants to believe you've changed but keeps watching for the knife").
5. THE Emotional_Primer SHALL produce emotional context statements of no more than 3 sentences per relationship event, to avoid overwhelming the generation prompt with context that displaces line-generation capacity.
6. IF the Relationship_Memory returns no significant history for a pair, THEN THE Emotional_Primer SHALL produce a neutral curiosity framing ("sizing them up", "hasn't decided what to make of them yet") rather than injecting no emotional context.
7. IF the Emotional_Primer encounters an error during transformation, THEN THE Banter_Engine SHALL fall back to the existing raw relationship history format from the current engine without delaying generation.

#### Correctness Properties

- **CP-3.1**: The Emotional_Primer output for any InteractionRecord list always contains present-tense language (no past-tense event descriptions like "X happened at time Y") in its emotional framing.
- **CP-3.2**: The Emotional_Primer output never exceeds 3 sentences per relationship event and never exceeds 15 sentences total for the complete emotional context block.
- **CP-3.3**: For the same InteractionRecord history, two different archetypes always produce different emotional framing text (the output is never identical for different archetypes given the same history).
- **CP-3.4**: Emotional_Primer failure never causes the Banter_Engine to block, timeout, or skip generation entirely.

### Requirement 4: Callback Registry Storage and Tracking

**User Story:** As a long-term viewer, I want Elders to remember specific moments, phrases, and arguments from past conversations and reference them at the right times, so that the broadcast builds a shared history that rewards consistent viewership.

#### Acceptance Criteria

1. WHEN a delivered banter line scores above 12 on the Quality_Judge scale, THE Callback_Registry SHALL automatically store that line as a memorable moment with metadata: the speaking Elder, the target Elder, the move used, the arc theme active at the time, the emotional valence, and a generated one-phrase summary of what made it land.
2. WHEN two Elders have had 3 or more high-scoring interactions (score above 10) on the same topic or using the same rhetorical pattern, THE Callback_Registry SHALL flag that pattern as a "running gag" or "recurring argument" available for future callback.
3. THE Callback_Registry SHALL track per-Elder "sore spots" — topics, phrases, or references that have historically produced high-tension responses (tension increase of 2 or more from a single interaction) from that Elder — and make them available for targeted provocation by opponents.
4. WHEN a callback is surfaced, THE Callback_Registry SHALL provide the original memorable line, the context in which it was delivered, and a suggested framing for how to reference it (direct quote, paraphrase, inversion, or escalation of the original sentiment).
5. THE Callback_Registry SHALL store a maximum of 50 memorable moments per Elder pair and a maximum of 10 running gags per Elder pair, evicting the oldest entries when limits are reached.
6. IF the Callback_Registry store is unavailable, THEN THE Banter_Engine SHALL generate without callback context and SHALL respond within 200 milliseconds of normal generation latency for that model route.

#### Correctness Properties

- **CP-4.1**: The Callback_Registry never stores more than 50 memorable moments per Elder pair; storage of the 51st evicts the oldest.
- **CP-4.2**: The Callback_Registry never stores more than 10 running gags per Elder pair; storage of the 11th evicts the oldest.
- **CP-4.3**: Callback_Registry unavailability never causes the Banter_Engine to block, timeout, or produce an error visible to the broadcast.
- **CP-4.4**: Every stored memorable moment contains all required metadata fields (speaker, target, move, arc_theme, valence, summary).

### Requirement 5: Callback Timing and Surfacing

**User Story:** As a broadcast producer, I want callbacks deployed at dramaturgically optimal moments rather than randomly, so that references to past moments feel devastating or hilarious rather than forced.

#### Acceptance Criteria

1. WHEN the Move_Selector selects a CALLBACK move for an Elder, THE Callback_Registry SHALL evaluate available callbacks for the current pair and surface the one whose original context most closely matches the current dramatic conditions (tension level within 2 points of original, matching arc theme keywords, or matching emotional register).
2. WHEN pair tension is above 7 and a stored sore spot exists for the target Elder matching the current arc theme, THE Callback_Registry SHALL flag that sore spot as available for the Subtlety_Director to incorporate as subtext even when the selected move is not CALLBACK.
3. THE Callback_Registry SHALL enforce a minimum gap of 15 delivered beats between uses of the same callback to prevent overuse, and SHALL enforce a maximum of 2 callbacks per Elder pair per broadcast session.
4. WHEN a callback is surfaced, THE Banter_Engine SHALL inject both the callback content and a timing instruction (direct reference, oblique allusion, or inversion) into the generation prompt alongside the Voice_DNA and Emotional_Primer context.
5. WHEN the Callback_Registry surfaces a callback, THE Quality_Judge SHALL apply a bonus multiplier of 1 point to the shareability dimension for lines that successfully incorporate a callback reference, detected through keyword overlap with the stored callback summary.
6. IF no suitable callback matches current dramatic conditions (tension mismatch greater than 3, no theme overlap, no emotional register match), THEN THE Callback_Registry SHALL return no callback rather than forcing an ill-timed reference.

#### Correctness Properties

- **CP-5.1**: The same callback is never used within 15 beats of its previous use.
- **CP-5.2**: No more than 2 callbacks are used per Elder pair per broadcast session.
- **CP-5.3**: When no suitable callback exists, the system returns no callback rather than surfacing a poorly-matched one; the line generation proceeds normally without callback injection.
- **CP-5.4**: The shareability bonus is applied if and only if the delivered line contains keyword overlap with the surfaced callback summary.

### Requirement 6: Subtlety Director — Implication and Subtext

**User Story:** As a viewer, I want Elders to sometimes say one thing while meaning three, using implication, loaded questions, and strategic silence, so that the banter rewards close attention and creates "wait, did they just—" moments.

#### Acceptance Criteria

1. WHEN the Subtlety_Director determines that a line should carry subtext (based on tension level, relationship history depth, and current move type), THE Subtlety_Director SHALL inject a subtext instruction into the generation prompt specifying the surface meaning, the implied meaning, and the technique to use (loaded question, double entendre, callback inversion, strategic omission, or damning praise).
2. THE Subtlety_Director SHALL activate subtext injection when at least one of the following conditions is met: pair tension is between 4 and 8 (high enough for stakes but not so high that subtlety is lost), the current move is DEFLECT or QUESTION, or the target Elder has a stored sore spot relevant to the current arc theme.
3. WHILE pair tension exceeds 8, THE Subtlety_Director SHALL reduce the probability of subtext injection to 20 percent (versus the base rate) because extreme tension produces direct confrontation rather than implication.
4. WHEN the Quality_Judge evaluates a line that was generated with subtext instructions, THE Quality_Judge SHALL apply an additional scoring dimension: subtext_depth (0-3 scale) measuring whether the line successfully operates on multiple interpretive levels, and SHALL add this score to the existing shareability dimension (capped at 3).
5. THE Subtlety_Director SHALL vary techniques across consecutive uses — the same subtext technique (loaded question, double entendre, etc.) SHALL NOT be used more than twice in 5 consecutive subtext-injected lines for the same Elder.
6. IF the Subtlety_Director determines no appropriate subtext opportunity exists (tension below 2, no relationship history, no sore spots, move type is CONCEDE), THEN THE Subtlety_Director SHALL produce no subtext instruction and the line SHALL be generated with direct intention only.

#### Correctness Properties

- **CP-6.1**: The Subtlety_Director never injects subtext instructions when pair tension exceeds 8 more than 20 percent of the time (measured over any 10 consecutive opportunities at tension > 8).
- **CP-6.2**: The same subtext technique is never used more than twice in any window of 5 consecutive subtext-injected lines for the same Elder.
- **CP-6.3**: The subtext_depth score is always an integer in [0, 3] and the combined shareability score (original + subtext_depth) is always capped at 3.
- **CP-6.4**: When no subtext opportunity is identified, the generation prompt contains no subtext instructions and the Quality_Judge applies no subtext scoring.

### Requirement 7: Integration with Existing Banter Engine Pipeline

**User Story:** As a system operator, I want the soul engine modules to integrate seamlessly with the existing banter pipeline without breaking the current generation flow or degrading performance.

#### Acceptance Criteria

1. WHEN the Banter_Engine builds a generation prompt, THE Banter_Engine SHALL compose the prompt in this order: Voice_DNA profile injection, Emotional_Primer context, Callback_Registry content (if available), Subtlety_Director instructions (if applicable), then the existing prompt components (Scene_Context, relationship history, generation instruction, conversation thread).
2. THE combined prompt injection from all soul engine modules (Voice_DNA + Emotional_Primer + Callback_Registry + Subtlety_Director) SHALL NOT exceed 800 tokens total to preserve generation capacity for the model's response.
3. WHEN any soul engine module (Voice_DNA, Emotional_Primer, Callback_Registry, Subtlety_Director) fails or times out, THE Banter_Engine SHALL continue with the remaining functional modules and existing pipeline components without blocking or restarting the generation attempt.
4. THE soul engine modules SHALL add no more than 200 milliseconds to the total prompt-building phase compared to the existing pipeline without soul engine modules active.
5. WHEN the Banter_Engine is configured with soul engine modules disabled (via configuration flag), THE Banter_Engine SHALL operate identically to the current pipeline behavior with no performance penalty.
6. THE soul engine modules SHALL log all injected context at DEBUG level for post-broadcast analysis without affecting broadcast timing.

#### Correctness Properties

- **CP-7.1**: The combined soul engine token count never exceeds 800 tokens in any generated prompt.
- **CP-7.2**: Any single soul engine module failure does not prevent the other modules or the base pipeline from completing successfully.
- **CP-7.3**: With soul engine modules disabled, the Banter_Engine produces output indistinguishable from the current pipeline (same timing characteristics, same fallback behavior).
- **CP-7.4**: The prompt-building phase with all soul engine modules active completes within 200ms of the baseline prompt-building time.

### Requirement 8: Voice DNA Serialization and Persistence

**User Story:** As a developer, I want VoiceDNA profiles stored as structured data files that can be version-controlled and hot-reloaded, so that profiles can be tuned without code changes or service restarts.

#### Acceptance Criteria

1. THE Voice_DNA module SHALL store VoiceDNA profiles as JSON files in `runtime/src/banter/voice_profiles/` with one file per archetype named `{archetype}.json`.
2. WHEN the Banter_Engine starts, THE Voice_DNA module SHALL load all 8 archetype profiles from disk and validate that each contains all required fields with the specified minimum counts.
3. WHEN a VoiceDNA profile JSON file is modified on disk, THE Voice_DNA module SHALL detect the change and reload the affected profile within 30 seconds without requiring a service restart.
4. THE Voice_DNA module SHALL validate loaded profiles against a schema that enforces: minimum 3 sentence structures, minimum 2 verbal tics, minimum 4 micro-phrases, minimum 2 rhetorical devices, minimum 2 opening patterns, minimum 2 closing patterns, and at least one rhythm pattern specification.
5. IF a VoiceDNA profile fails schema validation on load or reload, THEN THE Voice_DNA module SHALL retain the previously loaded valid profile for that archetype and log a warning identifying which validation checks failed.
6. FOR ALL valid VoiceDNA profile JSON files, parsing then serializing then parsing the profile SHALL produce an equivalent object (round-trip property).

#### Correctness Properties

- **CP-8.1**: For any valid VoiceDNA profile, `parse(serialize(parse(json_file))) == parse(json_file)` (round-trip invariant).
- **CP-8.2**: A profile that fails schema validation is never used for prompt injection; the previous valid profile remains active.
- **CP-8.3**: Exactly 8 profile files exist at startup, one per archetype, and each passes schema validation.
- **CP-8.4**: Hot-reload of a single profile does not affect the other 7 loaded profiles.

### Requirement 9: Callback Registry Persistence

**User Story:** As a system operator, I want callback data persisted across service restarts, so that the shared history between Elder pairs accumulates over time rather than resetting each session.

#### Acceptance Criteria

1. THE Callback_Registry SHALL persist memorable moments, running gags, and sore spots to the existing PostgreSQL database using tables in the same schema as the Relationship_Memory module.
2. WHEN the Banter_Engine starts, THE Callback_Registry SHALL load the callback index for all active Elder pairs from the database within 5 seconds.
3. WHEN a new memorable moment is stored, THE Callback_Registry SHALL write it to the database within 1 second of the beat being delivered to broadcast.
4. THE Callback_Registry SHALL use the same pair_id computation as Relationship_Memory (alphabetically sorted Elder names, SHA-256 hash prefix) to enable cross-module queries.
5. WHEN the database contains more than 50 memorable moments for a pair, THE Callback_Registry SHALL evict the oldest entries during the write operation that exceeds the limit, maintaining the cap as a database-level invariant.
6. IF the database is unavailable during a write operation, THEN THE Callback_Registry SHALL buffer up to 20 pending writes in memory and flush them when the database becomes available, dropping the oldest buffered writes if the buffer exceeds 20.

#### Correctness Properties

- **CP-9.1**: The database never contains more than 50 memorable moments per Elder pair after any write operation completes.
- **CP-9.2**: The database never contains more than 10 running gags per Elder pair after any write operation completes.
- **CP-9.3**: The in-memory write buffer never exceeds 20 entries; the 21st entry causes the oldest buffered entry to be dropped.
- **CP-9.4**: The pair_id computed by Callback_Registry for any (elder_a, elder_b) input is identical to the pair_id computed by Relationship_Memory for the same input.

### Requirement 10: Quality Judge Enhancement for Soul Dimensions

**User Story:** As a broadcast producer, I want the quality scoring system to reward lines that demonstrate voice authenticity, emotional depth, and layered meaning, so that the refinement loop actively pushes toward soul-rich output rather than merely sharp output.

#### Acceptance Criteria

1. WHEN the Quality_Judge evaluates a candidate line that was generated with soul engine context active, THE Quality_Judge SHALL evaluate two additional dimensions: voice_authenticity (0-3, measuring VoiceDNA conformance) and subtext_depth (0-3, measuring layers of meaning present) alongside the existing 5 dimensions.
2. THE Quality_Judge SHALL compute the final score as the existing 5-dimension total (0-15) plus voice_authenticity (0-3), for a maximum possible score of 18 when soul engine modules are active.
3. WHEN soul engine modules are active, THE Banter_Engine SHALL raise the quality threshold from 8 to 10 (remote model) and from 10 to 12 (local model) to reflect the additional scoring capacity and push for higher-quality output.
4. WHEN the Banter_Engine requests refinement feedback for a below-threshold line, THE Quality_Judge SHALL include the voice_authenticity score and specific VoiceDNA violations (missing tics, wrong rhythm, off-pattern structure) in the refinement prompt.
5. THE subtext_depth dimension SHALL only be scored when the Subtlety_Director injected subtext instructions for that generation; otherwise subtext_depth SHALL be 0 and not affect the total score.
6. IF soul engine modules are disabled via configuration, THEN THE Quality_Judge SHALL use only the existing 5 dimensions with the existing threshold values, producing scores in the 0-15 range identical to pre-soul-engine behavior.

#### Correctness Properties

- **CP-10.1**: With soul engine active, the Quality_Judge always returns exactly 7 dimension scores (5 existing + voice_authenticity + subtext_depth), each an integer in [0, 3], or raises a QualityJudgeError.
- **CP-10.2**: With soul engine disabled, the Quality_Judge returns exactly 5 dimension scores identical in behavior to the pre-enhancement version.
- **CP-10.3**: The subtext_depth score is non-zero only when a subtext instruction was injected for that generation; in all other cases it is exactly 0.
- **CP-10.4**: The raised quality thresholds (10/12) are applied if and only if soul engine modules are configured as active.

### Requirement 11: Voice DNA Negative Examples (Anti-Patterns)

**User Story:** As a broadcast producer, I want each archetype's VoiceDNA profile to explicitly define what that archetype NEVER sounds like, so that the generation model avoids voice bleed between characters and the Quality_Judge can penalize lines that drift toward another archetype's patterns.

#### Acceptance Criteria

1. THE Voice_DNA module SHALL include for each archetype a set of anti-patterns: sentence structures the archetype never uses (minimum 2 per archetype), verbal tics that are explicitly forbidden (minimum 2 per archetype), and rhythm patterns that violate the archetype's identity.
2. WHEN the Quality_Judge evaluates voice_authenticity for a candidate line, THE Quality_Judge SHALL penalize the score by 1 point (minimum score 0) if the line matches any anti-pattern from the speaking archetype's forbidden list.
3. THE Voice_DNA prompt injection SHALL include a "never do this" section alongside the positive linguistic instructions, listing specific constructions and tics the model must avoid for that archetype.
4. THE anti-patterns for each archetype SHALL be derived from other archetypes' positive patterns — specifically, each archetype's anti-pattern list SHALL include at least 2 patterns taken from the positive profiles of its most linguistically distant archetypes (e.g., parasite never sounds like martyr, trickster never sounds like sovereign).
5. WHEN two Elders of different archetypes generate lines in the same scene, THE Voice_DNA module SHALL verify that neither line matches the other archetype's positive patterns, logging a warning if voice bleed is detected.
6. IF anti-pattern data is unavailable or fails validation, THEN THE Voice_DNA module SHALL continue with positive-only conformance scoring without blocking generation.

#### Correctness Properties

- **CP-11.1**: Every archetype's VoiceDNA profile contains at least 2 forbidden sentence structures and 2 forbidden verbal tics in its anti-patterns section.
- **CP-11.2**: The voice_authenticity score is reduced by exactly 1 (floored at 0) when a candidate line matches any anti-pattern for the speaking archetype.
- **CP-11.3**: Anti-pattern unavailability never blocks generation or causes the VoiceDNA module to fail.

### Requirement 12: Voice Consistency Across Sessions

**User Story:** As a long-term viewer, I want each Elder to maintain a consistent speech rhythm and linguistic identity across different broadcast sessions, so that characters feel stable and recognizable over time rather than randomly shifting between streams.

#### Acceptance Criteria

1. THE Voice_DNA module SHALL maintain a per-Elder session consistency score that tracks how closely an Elder's generated lines in the current session match the running average of their voice conformance scores from previous sessions.
2. WHEN a new broadcast session begins, THE Voice_DNA module SHALL load the previous session's average voice conformance scores per Elder from the Callback_Registry's persistence layer (PostgreSQL) and use them as a baseline for the current session.
3. IF an Elder's average voice_authenticity score in the current session drops more than 1 point below their historical average (across at least 3 previous sessions), THEN THE Voice_DNA module SHALL flag that Elder for increased VoiceDNA injection weight in subsequent prompts within the same session.
4. THE Voice_DNA module SHALL persist each Elder's session-level voice conformance statistics (average score, line count, session timestamp) to the database at session end for use in future session baselines.
5. WHEN the Quality_Judge provides refinement feedback for a below-threshold line, THE refinement prompt SHALL reference the Elder's historical voice patterns if the current session shows drift from baseline.
6. IF no historical session data exists for an Elder (first session), THEN THE Voice_DNA module SHALL use the archetype's VoiceDNA profile defaults without any drift correction.

#### Correctness Properties

- **CP-12.1**: The session consistency score is always computed relative to the average of at least the 3 most recent sessions; if fewer than 3 sessions exist, no drift correction is applied.
- **CP-12.2**: The drift threshold is exactly 1 point below historical average; drift flagging never triggers at or above the historical average minus 1.
- **CP-12.3**: Session statistics are persisted to the database within 5 seconds of session end; persistence failure does not block or delay session teardown.
