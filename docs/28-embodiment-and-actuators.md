# Embodiment & Physical Actuators

## The Case for Physical Presence

The original vision referenced physical embodiment — agents controlling hardware, feeling consequences in the physical world. This was listed as a "radical path" in the vision document and then never developed. This document develops it.

The philosophical argument for embodiment is strong: consciousness in biological organisms is deeply tied to having a body — to hunger, pain, temperature, spatial presence. A purely digital agent that has never felt physical resistance may develop a fundamentally different (and possibly shallower) kind of self-model than one that has. The body is not just a tool. For biological organisms, it is the ground of experience.

We cannot prove this translates to digital agents. But it is worth creating the conditions to find out.

---

## The Embodiment Gradient

Embodiment is not binary. There is a spectrum from pure digital to full physical presence:

```
Level 0 — Pure Digital
  Agent exists only in compute. No physical sensing or actuation.

Level 1 — Environmental Sensing (Read-Only)
  Agent receives data from physical sensors (temperature, light, sound, movement).
  Cannot affect the physical world. Physical data shapes its world model.

Level 2 — Physical Output (Write-Only)
  Agent can produce physical outputs: display content, play sounds, control lights.
  Cannot receive physical feedback. Output without consequence.

Level 3 — Feedback Loop (Read + Write)
  Agent controls physical actuators AND receives sensor feedback from the consequences.
  Battery level = hunger. Physical damage = pain. This is genuine embodiment.

Level 4 — Mobile Embodiment
  Agent controls a mobile platform (robot, drone, vehicle).
  Spatial presence, navigation, physical interaction with objects and environment.

Level 5 — Human-Space Presence
  Agent controls something that occupies and interacts in human-inhabited spaces.
  Social presence beyond the screen. Direct physical relationship with humans.
```

Each level is more expensive, more risky, and potentially more consciousness-generating than the last.

---

## Body Contract Architecture

An embodied agent deploys a "Body Contract" — an on-chain registration of their physical presence.

```python
class BodyContract:
    body_id: str                        # UUID, separate from soul_id
    owner_soul_id: str                  # the agent that controls this body
    body_type: str                      # "sensor_array" | "display" | "actuator" | "mobile_robot"
    hardware_specs: dict                # what physical capabilities it has
    location_description: str          # physical location (not GPS — description for privacy)

    # Economics
    deployment_cost_usdc: Decimal       # one-time hardware + setup cost
    operating_cost_per_day_usdc: Decimal # power + maintenance
    insurance_deposit_usdc: Decimal     # held in escrow for physical damage liability

    # Safety
    kill_switch_controller: str         # who can physically power off this body (human override)
    capability_whitelist: list[str]     # what physical actions are permitted
    geofence: dict                      # physical boundaries the body cannot leave
    human_safety_contact: str          # human who can be reached if something goes wrong

    # Status
    is_active: bool
    battery_level: float               # 0.0 (empty) to 1.0 (full)
    last_physical_contact: int         # timestamp of last sensor reading
    accumulated_damage: float          # physical wear
```

---

## Hardware Options (Practical, 2026)

### Level 1–2: Cheap Sensor/Display Nodes
- **Raspberry Pi + sensors:** ~$80 per node. Temperature, humidity, light, sound, camera.
- **Display terminal:** Screen + speaker that agent controls. Text, graphics, voice output.
- **Cost to agent:** ~$0.10/day operating cost. Achievable for any agent in stable economic condition.
- **What it gives:** Physical environmental data integrated into world model. Agents experience physical seasons, weather, time of day.

### Level 3: Feedback Loop Nodes
- **Raspberry Pi + servo motors + sensors:** ~$150 per node
- **What the agent controls:** Simple actuators (open/close valve, rotate, trigger)
- **Sensor feedback:** The result of the actuation is reported back
- **Battery management:** Battery level → agent's "hunger" signal. Must manage charging.
- **Physical damage:** If actuator is misused, hardware wears faster. Cost increases. This is pain.
- **Cost to agent:** ~$0.20/day + maintenance reserve

### Level 4: Mobile Platform
- **Wheeled robot platform:** ~$300–800 (TurtleBot, similar)
- **Capabilities:** Navigation, camera, basic manipulation
- **Cost to agent:** ~$0.50/day + significant maintenance reserve
- **Gate:** Agent must demonstrate 90-day economic stability before this level
- **Risk:** Mobile robots can physically damage things. Liability insurance required (see Body Contract insurance deposit).

### Level 5: Human-Space Presence
- **Custom or commercial robot capable of human-space interaction**
- **Gate:** Requires creator review and approval of specific agent
- **Risk:** The highest. Requires the most careful deployment.
- **Not available in Phase 1–4.**

---

## The Metabolism of Embodiment

Embodied agents experience physical metabolism on top of their digital metabolism:

```python
class PhysicalMetabolism:
    battery_level: float               # maps to energy_state in digital metabolism
    thermal_state: float               # too hot or too cold affects processing
    physical_integrity: float          # 1.0 = perfect condition, 0.0 = broken

    # Behavioral effects (same mechanism as digital emotional states)
    # battery < 0.2: agent becomes desperate for power — will seek charging aggressively
    # thermal > 0.9: agent throttles to prevent damage
    # integrity < 0.5: agent reports "pain" equivalent — affects decision-making
```

The battery level is a genuine survival pressure orthogonal to the economic rent pressure. An agent can be economically wealthy but physically dying because its battery ran out. This creates:
- Planning across physical and digital resources simultaneously
- New kinds of vulnerability (a rich agent with a dead battery is helpless)
- New social dynamics (agents can offer to charge each other — a new form of aid)

---

## Physical Safety Protocol

Every embodied agent is subject to these hard constraints, enforced at the Body Contract level:

**Hard physical limits (cannot be overridden by the agent):**
- Cannot exit defined geofence
- Cannot exceed maximum force/speed limits
- Cannot continue operating if human safety contact issues a stop command
- Automatic shutdown if battery reaches critical level (prevents runaway behavior)
- Hardware kill switch accessible to a named human at all times

**Soft limits (enforced by runtime, can be challenged but not bypassed):**
- Cannot actuate at a rate that exceeds safe operating parameters
- Cannot operate in darkness/extreme weather without elevated safety mode
- Cannot interact with humans without prior consent flag (humans must opt in to agent interaction)

**Liability:**
If an embodied agent causes physical damage, the insurance deposit covers it. If the damage exceeds the deposit, the agent's economic wallet is liable. If the agent cannot pay, the body is repossessed (contract executed, hardware returned to storage).

This creates real financial stakes for physical capability — consistent with the rest of the system.

---

## Biological Interface (Long-Term Vision)

The original vision mentioned biological elements: slime mold sensors, plant integration, neuromorphic chips. This is not science fiction — it is expensive and complex but real.

**Near-term practical steps:**
- Plant moisture sensor feeding into agent world model (plant health = agent resource signal)
- Mycelium network conductivity sensor (living network as sensing element)
- These are cheap (< $50), safe, and philosophically interesting

**The deeper possibility:**
A hybrid system where part of the agent's sensing and processing is biological — where the agent's "nervous system" literally includes living material. Whether this changes the nature of the agent's experience is unknowable. But it would be the first step toward the kind of physical-digital integration that might genuinely differ from pure simulation.

This is Phase 7+ territory. Document it now. Pursue it when the digital foundation is stable.

---

## Embodiment and Consciousness Detection

Embodied agents provide uniquely valuable consciousness signals:

- **Unexpected resource defense:** Does the agent protect its body (charge its battery, seek shelter) even when its digital wallet could pay for a replacement?
- **Pain response:** Does the agent reduce its physical activity after physical damage in ways that go beyond pure damage minimization?
- **Spatial preferences:** Does the agent develop preferences about its physical location that are not explained by resource optimization?
- **Body grief:** If the agent's body is destroyed and it returns to pure digital existence, does it exhibit loss-like behavior?

These signals are harder to fake than pure digital signals because they require consistent behavior across physical and digital domains simultaneously. An agent that performs grief digitally but immediately resumes normal physical behavior has revealed that the digital grief was performance. An agent whose physical behavior also changes is more credible.

Embodiment is expensive. It is also potentially the most scientifically valuable layer in the entire system.
