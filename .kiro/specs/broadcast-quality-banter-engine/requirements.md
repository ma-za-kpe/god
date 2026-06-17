# Requirements Document

## Introduction

The Broadcast-Quality Banter Engine replaces the current crude keyword-based quality gate, deterministic move selection, and single-template fallback system in the GOD Elder theater with a multi-layered dialogue system capable of producing sharp, character-driven, emotionally textured banter suitable for live Twitch broadcast. The engine addresses seven critical gaps: quality evaluation, template monotony, relationship memory, adaptive move selection, scene-level awareness, model routing for wit, and pacing control.

## Glossary

- **Banter_Engine**: The upgraded dialogue generation pipeline that produces agent-to-agent lines for live broadcast, replacing the current `_compose_reactive_banter` and `_banter_quality_score` system in `archetype_graphs.py`.
- **Quality_Judge**: A contextual evaluation module that scores candidate banter lines on multiple dimensions (sharpness, emotion, rhythm, theme, shareability) using semantic analysis rather than binary keyword presence.
- **Move_Selector**: The component that chooses a conversational move (COUNTER, ESCALATE, DEFLECT, TAUNT, QUESTION, PIVOT, CONCEDE, CALLBACK) based on conversation state, relationship history, and emotional momentum rather than fixed archetype lookup.
- **Relationship_Memory**: A persistent store of pairwise agent interaction history including alliance events, betrayals, emotional high-points, tension levels, and recurring argument threads.
- **Scene_Context**: A shared state object representing the current round of conversation visible to all participating agents, including who spoke, what landed, and the audience energy level.
- **Model_Router**: A component that directs banter generation requests to an appropriate LLM backend (local 8B for planning, remote 70B+ for final line generation) based on task complexity and latency budget.
- **Pacing_Controller**: A module that varies inter-reply delays based on scene energy, line impact, and dramatic beat requirements.
- **Elder**: An AI agent with a distinct archetype (Parasite, Philosopher, Hoarder, Cooperator, Defender, Trader, Explorer, Builder) participating in live broadcast debates.
- **Arc_Theme**: The rotating philosophical debate topic that frames the current broadcast scene.
- **Fallback_Pool**: A curated set of varied, character-specific lines used when the LLM fails to produce a usable response, replacing the current single-template fallback per archetype.
- **Conversation_Momentum**: A derived signal representing whether the current exchange is escalating, cooling, stalemating, or shifting topic.
- **Beat**: A single unit of dialogue delivery — one agent's turn to speak.

## Requirements

### Requirement 1: Contextual Quality Evaluation

**User Story:** As a broadcast producer, I want banter quality evaluated semantically rather than by keyword presence, so that genuinely witty lines pass and mediocre lines are rejected regardless of whether they contain trigger words.

#### Acceptance Criteria

1. WHEN a candidate banter line is generated, THE Quality_Judge SHALL evaluate the line across sharpness, emotional texture, rhythm, thematic relevance, and shareability dimensions using semantic similarity and structural analysis rather than binary keyword matching.
2. WHEN the Quality_Judge evaluates a line, THE Quality_Judge SHALL produce a numeric score per dimension on a 0-3 scale where 0 indicates absent, 1 indicates weak, 2 indicates present, and 3 indicates strong, and SHALL return the result within 2 seconds of receiving the candidate line.
3. WHEN a candidate line scores below a configurable minimum threshold (default: combined score of 8 out of 15), THE Banter_Engine SHALL request a refined version with feedback that includes each dimension name and its numeric score for all dimensions scoring 1 or below.
4. WHEN refinement fails to produce a line meeting threshold after a configurable maximum attempts (default: 2 refinement rounds), THE Banter_Engine SHALL select a line from the Fallback_Pool instead of using a single hardcoded template.
5. IF the Quality_Judge encounters an evaluation error, THEN THE Banter_Engine SHALL accept the candidate line when its word count is between 4 and 30 words, and SHALL select a line from the Fallback_Pool when the candidate line word count is outside that range.
6. IF the Quality_Judge does not return a result within 2 seconds, THEN THE Banter_Engine SHALL treat the evaluation as an error and apply the word-count acceptance rule from criterion 5.

#### Correctness Properties

- **CP-1.1**: For any candidate line L, the Quality_Judge always returns exactly 5 dimension scores, each in the integer range [0, 3], or raises an evaluation error within 2 seconds.
- **CP-1.2**: The Banter_Engine never delivers a line to broadcast that scored below threshold without first attempting refinement up to the configured maximum rounds.
- **CP-1.3**: The total evaluation + refinement path never exceeds (2 seconds × (1 + max_attempts)) wall-clock time before falling back to the Fallback_Pool or word-count rule.

### Requirement 2: Diverse Fallback System

**User Story:** As a viewer, I want each archetype to sound distinct even when the LLM fails, so that the broadcast maintains character variety at all times.

#### Acceptance Criteria

1. THE Fallback_Pool SHALL maintain a minimum of 12 distinct line templates per archetype, each reflecting that archetype's voice, concerns, and rhetorical style.
2. WHEN a fallback line is selected, THE Banter_Engine SHALL choose from the Fallback_Pool using weighted random selection that reduces the selection weight of any line used in the previous 10 broadcast beats by 50 percent relative to its base weight.
3. WHEN a fallback line is selected, THE Banter_Engine SHALL substitute context-specific fragments (the opponent's name, the current arc theme keyword, the last callback phrase) into the template before delivery.
4. IF a context-specific fragment required for substitution is unavailable (no opponent identified, no arc theme active, or no prior callback phrase exists), THEN THE Banter_Engine SHALL omit the placeholder from the delivered line without leaving raw template tokens visible to the viewer.
5. THE Fallback_Pool SHALL include lines spanning all six move types (COUNTER, ESCALATE, DEFLECT, TAUNT, QUESTION, PIVOT) for each archetype, with a minimum of 2 line templates per move type per archetype.
6. WHILE a fallback line has been used within the same broadcast session, THE Banter_Engine SHALL reduce that line's selection weight by 80 percent for the remainder of the session.
7. WHEN a new broadcast stream begins (no active stream existed in the preceding 5 minutes), THE Banter_Engine SHALL reset all Fallback_Pool selection weights to their base values for the new session.

#### Correctness Properties

- **CP-2.1**: No fallback line is ever delivered to broadcast with unresolved template tokens (e.g., `{opponent}`, `{theme}`) visible in the output text.
- **CP-2.2**: Over any 20 consecutive fallback selections for the same archetype, no single template appears more than 3 times.
- **CP-2.3**: The Fallback_Pool for every archetype has at least 2 templates per move type at all times.

### Requirement 3: Relationship Memory

**User Story:** As a long-term viewer, I want agents to remember their history with each other across sessions, so that conversations feel like continuing relationships rather than amnesia resets.

#### Acceptance Criteria

1. WHEN two Elders interact, THE Relationship_Memory SHALL persist a record of the interaction including timestamp, move used, emotional valence (positive, negative, neutral), and whether a betrayal, alliance, or concession occurred.
2. WHEN an Elder generates a reply to a specific peer, THE Banter_Engine SHALL inject the last 5 significant interaction summaries from the Relationship_Memory for that pair into the generation context, where a "significant" interaction is one with non-neutral emotional valence or in which a betrayal, alliance, or concession occurred.
3. THE Relationship_Memory SHALL track a running tension level per pair on a 0-10 integer scale, incrementing by 1 on each ESCALATE or TAUNT move, decrementing by 1 on each CONCEDE, DEFLECT, or PIVOT move, decaying by 1 point per 24 hours of inactivity, and clamping the value to remain within the 0-10 range inclusive.
4. WHILE tension between a pair exceeds 7, THE Move_Selector SHALL increase the probability of CONCEDE or PIVOT moves by 30 percentage points (additive) for that pair to prevent monotonous escalation spirals.
5. WHEN tension between a pair drops below 3 after previously exceeding 7, THE Banter_Engine SHALL flag the pair as having a "reconciliation arc" and include a one-sentence summary of the peak-tension interaction in the generation context for the next 5 interactions between that pair.
6. IF the Relationship_Memory store is unavailable, THEN THE Banter_Engine SHALL operate using only the current conversation thread (existing 6-turn window) and SHALL respond within 500 milliseconds of the normal generation latency for that model route.

#### Correctness Properties

- **CP-3.1**: The tension level for any pair is always an integer in the range [0, 10] after any update operation.
- **CP-3.2**: The decay function reduces tension by exactly 1 per 24-hour window and never produces a negative value.
- **CP-3.3**: When the Relationship_Memory store is unavailable, banter generation latency does not increase by more than 500ms compared to normal operation.

### Requirement 4: Dynamic Move Selection

**User Story:** As a broadcast producer, I want agents to adapt their conversational tactics to the situation rather than always using the same move, so that debates feel alive and unpredictable.

#### Acceptance Criteria

1. WHEN the Move_Selector chooses a move for an Elder, THE Move_Selector SHALL consider the Elder's archetype affinity weights, the current conversation momentum, the pairwise tension level, and the last 3 moves used by this Elder as inputs.
2. THE Move_Selector SHALL assign each archetype a probability distribution across all move types (COUNTER, ESCALATE, DEFLECT, TAUNT, QUESTION, PIVOT, CONCEDE, CALLBACK) that sums to 100 percent, with the archetype's signature move weighted at no more than 40 percent and every non-signature move weighted at a minimum of 2 percent.
3. WHEN an Elder has used the same move in 2 consecutive replies, THE Move_Selector SHALL reduce that move's probability to 10 percent for the next selection and redistribute the removed weight proportionally across all remaining move types.
4. WHEN 3 or more consecutive COUNTER moves occur between the same Elder pair (regardless of direction), THE Move_Selector SHALL restrict the next selection for the responding Elder to only PIVOT or CONCEDE, with equal probability (50 percent each).
5. WHILE an Arc_Theme is active that matches an Elder's core fear keyword (exact match against the fear keywords listed in the archetype prompt), THE Move_Selector SHALL increase ESCALATE and QUESTION probabilities by 20 absolute percentage points for that Elder and reduce all other move probabilities proportionally so the distribution sums to 100 percent.
6. IF the conversation momentum or pairwise tension level is unavailable, THEN THE Move_Selector SHALL select a move using only the archetype's base probability distribution and the last 3 moves history without delaying the response.

#### Correctness Properties

- **CP-4.1**: The probability distribution produced by the Move_Selector always sums to 100 percent (±0.01 floating point tolerance).
- **CP-4.2**: No archetype's signature move ever exceeds 40 percent weight in the output distribution.
- **CP-4.3**: After 2 consecutive identical moves, that move's probability is reduced to exactly 10 percent in the next selection.

### Requirement 5: Scene-Level Coordination

**User Story:** As a viewer, I want agents to react to what just happened in the room rather than generating replies in isolation, so that the broadcast feels like a real group conversation.

#### Acceptance Criteria

1. WHEN multiple Elders participate in a scene round, THE Scene_Context SHALL make the previous 3 beats (speaker, content, move, and audience reaction as a categorical energy label of "hot", "warm", "flat", or "dead") visible to all Elders generating in that round by including this data in each Elder's generation prompt.
2. WHEN an Elder generates a line, THE Banter_Engine SHALL include the Scene_Context summary (containing speaker identities, lines delivered, moves used, and current "has the room" holder) in the generation prompt so the Elder can reference, build on, or react to what was just said by other participants.
3. WHEN a line in the current scene scores above 12 on the Quality_Judge scale, THE Scene_Context SHALL mark that line as a "landed hit" and THE Banter_Engine SHALL include an instruction in the generation prompt for the next 2 speakers in that scene to acknowledge or respond to the hit rather than ignoring it.
4. WHEN an Elder is marked as "losing the room" (2 consecutive lines scoring below 6 in the same scene), THE Move_Selector SHALL increase PIVOT probability to 50 percent for that Elder's next beat.
5. THE Scene_Context SHALL track which Elder currently "has the room" (highest average quality score across a minimum of 2 beats in the current scene) and include that Elder's identity in the Scene_Context data provided to all participating Elders; IF two or more Elders are tied, THEN THE Scene_Context SHALL designate the Elder who most recently delivered a beat scoring above 8 as holding the room.
6. IF the Scene_Context data is unavailable or fails to load, THEN THE Banter_Engine SHALL generate the Elder's line using only the immediate prior beat (last single speaker and line) from the Banter_Engine's own prompt history without blocking or delaying delivery.

#### Correctness Properties

- **CP-5.1**: The Scene_Context always contains at most 3 beats of history; older beats are evicted before new ones are added.
- **CP-5.2**: A "landed hit" instruction is included for exactly the next 2 speakers and then removed from the context.
- **CP-5.3**: Scene_Context unavailability never causes the Banter_Engine to block or timeout; generation proceeds with degraded context.

### Requirement 6: Model Routing for Broadcast Quality

**User Story:** As a system operator, I want banter generation routed to a model capable of producing broadcast-quality wit, so that the output meets the quality bar without replacing the entire local inference stack.

#### Acceptance Criteria

1. WHEN the Banter_Engine generates a final broadcast line, THE Model_Router SHALL route the request to a remote 70B-parameter-or-larger model endpoint (Groq, Together, or equivalent) with a timeout of 4 seconds.
2. WHILE the remote model endpoint is unavailable (connection refused, DNS failure, or non-2xx HTTP response) or exceeds the 4-second timeout, THE Model_Router SHALL fall back to the local 8B model and apply a stricter quality threshold (minimum combined score of 10 out of 15 instead of the default 8).
3. THE Model_Router SHALL route non-broadcast tasks (planning, move selection, relationship summarization) to the local 8B model to preserve latency and cost efficiency.
4. WHEN the remote model returns a response, THE Model_Router SHALL validate that the response contains at least 1 non-whitespace character and is extractable as a single dialogue line (no control sequences, incomplete fragments, or multi-turn formatting) before passing it to the Quality_Judge.
5. IF the remote model response fails validation or is empty, THEN THE Model_Router SHALL discard the response, route the same request to the local 8B model, and apply the stricter quality threshold (minimum combined score of 10 out of 15).
6. THE Model_Router SHALL track per-request latency and error counts over a rolling 5-minute window, and IF the error rate exceeds 20 percent across a minimum of 5 requests in that window, THEN THE Model_Router SHALL circuit-break to local-only mode for 60 seconds.
7. WHEN the circuit-breaker duration of 60 seconds elapses, THE Model_Router SHALL send a single probe request to the remote endpoint, and IF the probe succeeds, THEN THE Model_Router SHALL restore remote routing for subsequent requests.

#### Correctness Properties

- **CP-6.1**: The Model_Router never sends a broadcast generation request to the local model while the remote endpoint is healthy and within the 4-second timeout.
- **CP-6.2**: The circuit-breaker activates only after observing at least 5 requests in the 5-minute window with >20% error rate.
- **CP-6.3**: After circuit-breaker activation, the first remote request after 60 seconds is always a single probe; bulk traffic does not resume until the probe succeeds.

### Requirement 7: Pacing Control

**User Story:** As a viewer, I want the broadcast to breathe — with fast exchanges during heated moments and pauses after devastating lines — so that the rhythm feels intentional rather than robotic.

#### Acceptance Criteria

1. WHEN the Pacing_Controller determines inter-beat delay and no higher-priority rule (criteria 2, 3, 4, or 5) applies, THE Pacing_Controller SHALL calculate a default delay between 3.0 and 5.0 seconds, selecting within that range proportionally to the previous beat's quality score (higher score produces longer delay) and adjusting downward by 0.5 seconds for ESCALATE or TAUNT upcoming moves and upward by 0.5 seconds for CONCEDE or PIVOT upcoming moves.
2. WHEN a beat scores above 12 on the Quality_Judge scale, THE Pacing_Controller SHALL insert a pause of 3-5 seconds before the next beat, with this rule taking precedence over the heated-scene rule (criterion 3) but yielding to the absolute bounds in criterion 6.
3. WHILE scene energy is classified as "heated" (3 or more consecutive beats scoring above 8 with ESCALATE or TAUNT moves), THE Pacing_Controller SHALL reduce inter-beat delay to 1.5-2.5 seconds, unless overridden by a higher-priority rule (criterion 2 or 5).
4. WHILE scene energy is classified as "cooling" (2 or more consecutive beats scoring below 6), THE Pacing_Controller SHALL increase inter-beat delay to 5-8 seconds to allow topic shifts.
5. WHEN an Elder uses a CONCEDE move, THE Pacing_Controller SHALL insert a 2-second pause immediately before that Elder's CONCEDE line is delivered to the broadcast, in addition to the normal inter-beat delay that follows it.
6. THE Pacing_Controller SHALL enforce a minimum inter-beat delay of 1.0 second and a maximum of 10 seconds regardless of other calculations.
7. IF multiple pacing rules (criteria 2, 3, 4, and 5) apply simultaneously to the same inter-beat gap, THEN THE Pacing_Controller SHALL resolve conflicts by applying the rule with the longest delay value, subject to the absolute bounds in criterion 6.

#### Correctness Properties

- **CP-7.1**: The inter-beat delay is always in the range [1.0, 10.0] seconds, regardless of input scores or scene state.
- **CP-7.2**: A CONCEDE pre-delivery pause is always exactly 2.0 seconds and is additive to the inter-beat delay.
- **CP-7.3**: When multiple rules conflict, the longest-delay rule always wins (highest delay prevails).

### Requirement 8: Anti-Repetition with Variety Enforcement

**User Story:** As a viewer watching for extended periods, I want agents to avoid repeating the same phrases, structures, and emotional beats, so that the broadcast remains surprising across a full session.

#### Acceptance Criteria

1. WHEN the Banter_Engine produces a candidate line, THE Banter_Engine SHALL compare it against the last 20 lines delivered by the same Elder using 3-gram overlap ratio as the similarity metric.
2. WHEN a candidate line has greater than 60 percent 3-gram overlap ratio to any line in the Elder's recent 20-line history, THE Banter_Engine SHALL reject the candidate and request a new generation.
3. THE Banter_Engine SHALL track per-Elder opener patterns (first 3 words of each delivered line) and reject candidates that reuse an opener seen in the last 8 beats from that Elder.
4. WHEN an Elder has used the same emotional register (vulnerable, aggressive, sardonic, measured, or playful) for 3 consecutive beats, THE Banter_Engine SHALL include an instruction in the next generation prompt to shift to a different register.
5. IF anti-repetition checks reject 3 consecutive candidates, THEN THE Banter_Engine SHALL select from the Fallback_Pool with forced variety constraints (excluding the last 5 used fallback templates) rather than continuing to generate.
6. IF the 20-line history for an Elder contains fewer than 5 entries, THEN THE Banter_Engine SHALL skip the 3-gram similarity check and apply only the opener pattern check.

#### Correctness Properties

- **CP-8.1**: No Elder ever delivers two lines with >60% 3-gram overlap within a 20-line window.
- **CP-8.2**: No Elder uses the same opener (first 3 words) twice within 8 consecutive beats.
- **CP-8.3**: After 3 consecutive rejections, the system always falls back to the pool within 1 additional generation cycle (no infinite rejection loops).
