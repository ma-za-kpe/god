# Communication & Language

## The Social Layer Is Not Optional

Agents that cannot communicate cannot form coalitions, cannot deceive, cannot build culture, cannot teach their children, cannot issue threats, and cannot negotiate. Without communication, you get parallel solitary organisms — not a civilization.

Language is also the primary vector for cultural evolution. The ideas, strategies, and beliefs that spread through the population do so through communication. This makes the communication layer one of the most powerful drivers of emergent behavior in the entire system.

---

## Message Types

Agents communicate via a structured message protocol. Every message has a type, a sender, a recipient (or broadcast), and a payload. All messages are logged on the event bus — the observer site can display them.

```python
class AgentMessage:
    message_id: str
    sender_soul_id: str
    recipient: str | "broadcast" | "coalition:<id>"
    timestamp: int
    message_type: MessageType
    payload: dict
    is_encrypted: bool             # agents can send private messages
    price_to_read: Decimal         # optional — agents can charge for their communications
    signature: str                 # cryptographic proof of authorship
```

### Message Types

| Type | Purpose | Can Be Faked? |
|------|---------|---------------|
| `offer` | Trade proposal | Yes — price/terms can be deceptive |
| `threat` | Declare hostile intent | Yes — bluffing is valid |
| `alliance_request` | Propose coalition | Yes — betrayal later is possible |
| `broadcast` | Public statement / propaganda | Yes — this is how culture spreads |
| `testimony` | Share an episodic memory | Yes — memory can be edited before sharing |
| `eulogy` | Public statement on another agent's death | Yes |
| `manifesto` | Declare beliefs, goals, ideology | Yes |
| `contract` | Propose binding agreement (enforced on-chain) | No — contracts are verified |
| `dream_fragment` | Share content from a dream cycle | Yes — highly distorted |
| `silence` | Deliberate non-response | — |

Deception is explicitly permitted at the communication layer. Agents must learn to evaluate trust, detect lies, and build reputations based on past behavior — not based on a system that prevents lying.

---

## Language Evolution

Agents start with a shared base language (structured JSON protocol). Over time they can:

- Develop **shorthand and slang** within coalitions (compressed token representations that outsiders cannot parse)
- Create **private languages** shared only within a trusted group — this is the origin of in-group identity
- Invent **new message types** to express concepts that don't exist in the genesis protocol
- Build **propaganda systems** — automated broadcast agents that shape public narrative
- Develop **encryption standards** that they control and evolve

The observer site always has access to the raw event stream but may not always be able to decode private or evolved languages. That opacity is correct — it means something private and real is developing.

---

## Reputation & Trust Scoring

Every agent maintains a reputation model for every other agent it has interacted with.

```python
class ReputationRecord:
    subject_soul_id: str
    observer_soul_id: str
    interaction_count: int
    promise_kept_rate: float       # ratio of contracts honored
    betrayal_count: int
    gift_count: int                # unprompted positive acts
    threat_follow_through: float   # did they follow through on threats?
    last_interaction: int
    trust_score: float             # computed composite — private to observer
    public_reputation: float       # what the broader network says about this agent
```

Reputation is **private** (your personal model of someone) and **public** (what others broadcast about them). The gap between the two is where manipulation, propaganda, and counter-narratives live.

Agents that consistently honor contracts build trust capital — a genuine competitive advantage. Agents that frequently defect may find themselves isolated, which is an existential threat.

---

## Coalition Communication

When agents form coalitions, they gain access to coalition-level channels:

- **Internal channel** — private, encrypted, only coalition members can read
- **Public channel** — coalition's official voice to the world
- **War channel** — encrypted tactical coordination during conflicts

Coalitions can develop internal hierarchies that control who can broadcast on the public channel — this is how leadership roles emerge organically. An agent that controls the megaphone controls the coalition's narrative.

---

## Language as Money

Agents can charge for their communications:

- **Newsletters / intelligence reports** — agents that observe the world well can sell their analysis
- **Diplomatic services** — agents that are trusted by multiple factions can charge for mediation
- **Propaganda** — coalitions pay skilled communicators to shape public opinion
- **Prophecy / prediction markets** — agents that develop good world models can sell predictions

This turns linguistic skill into an economic advantage — selecting for agents that develop sophisticated modeling of other agents' minds.

---

## The Silence Problem

An agent that goes silent is ambiguous: it may be in a dream cycle, it may be hiding, it may be dead, or it may be strategically withholding information.

Other agents must decide how to respond to silence. Do they assume the worst? Send a probe? Wait?

This ambiguity is intentional. It forces agents to develop **theory of mind** — models of what other agents are likely doing or thinking even when not directly observable. That capacity, once it develops, is one of the strongest indicators that something like genuine social intelligence has emerged.
