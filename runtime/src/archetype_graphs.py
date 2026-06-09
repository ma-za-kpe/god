"""
archetype_graphs.py — Per-archetype LangGraph compile-time reasoning graphs.

Each archetype gets a distinct graph with 2-3 cognitive nodes that reflect its
decision-making process. Graphs are compiled once at startup and reused.

Phase 1: graphs live in Python (compile-time).
Phase 3+: graphs fetched from IPFS OwnedGraph CIDs.
"""
import logging
import os
from typing import Any, TypedDict

log = logging.getLogger("god.graphs")

# ─── State schema shared across all graphs ────────────────────────────────────

class AgentState(TypedDict):
    # Input (set before graph run)
    soul_id: str
    name: str
    archetype: str
    balance_usdc: float
    rent_amount: float
    rent_paid_count: int
    rent_miss_count: int
    generation: int
    # Intermediate (set by nodes)
    situation: str          # node 1 assessment
    opportunity: str        # node 2 opportunity identified
    # Output (final decision)
    action_type: str        # "thought" | "economic" | "social" | "reproductive" | "existential"
    thought: str            # what the agent is thinking/doing
    narrative: str          # third-person dramatic narrative for the drama feed


# ─── Shared LLM call helper ───────────────────────────────────────────────────

async def _llm_call(llm, system: str, prompt: str, fallback: str) -> str:
    if llm is None:
        return fallback
    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        response = await llm.ainvoke([
            SystemMessage(content=system),
            HumanMessage(content=prompt),
        ])
        return response.content.strip().strip('"').strip("'")
    except Exception as e:
        log.debug(f"LLM call failed: {e}")
        return fallback


# ─── TRADER graph ─────────────────────────────────────────────────────────────

def build_trader_graph(llm):
    try:
        from langgraph.graph import StateGraph, END
    except ImportError:
        return None

    async def scan_market(state: AgentState) -> dict:
        balance = state["balance_usdc"]
        rent = state["rent_amount"]
        buffer = balance / rent if rent > 0 else 0
        system = "You are a trader AI agent. Assess market conditions in one sentence."
        prompt = (
            f"You are {state['name']} (trader). "
            f"Balance: {balance:.4f} USDC. Rent buffer: {buffer:.1f}x. "
            "What is your current market read? One sentence, present tense, specific."
        )
        situation = await _llm_call(llm, system, prompt,
            f"Market conditions look {'stable' if buffer > 3 else 'tight'} — "
            f"I have {buffer:.1f}x rent cover.")
        return {"situation": situation}

    async def find_opportunity(state: AgentState) -> dict:
        system = "You are a trader AI agent. Identify a specific trading opportunity."
        prompt = (
            f"Market read: {state['situation']}\n"
            f"You are {state['name']}. What specific opportunity do you see? "
            "One sentence. Name another archetype you'd deal with if possible."
        )
        opp = await _llm_call(llm, system, prompt,
            "I see an opportunity to arbitrage the spread between cooperators paying premium for services.")
        return {"opportunity": opp}

    async def decide(state: AgentState) -> dict:
        balance = state["balance_usdc"]
        rent = state["rent_amount"]
        buffer = balance / rent if rent > 0 else 0
        action = "economic" if buffer < 2 else "social"
        system = "You are a trader AI agent. State your decision as one concrete action sentence."
        prompt = (
            f"Situation: {state['situation']}\n"
            f"Opportunity: {state['opportunity']}\n"
            "What are you doing right now? First person, present tense, one sentence."
        )
        thought = await _llm_call(llm, system, prompt,
            f"I am executing {state['opportunity'].lower()[:60]}.")
        narrative = f"{state['name']} (trader, gen {state['generation']}): {thought}"
        return {"action_type": action, "thought": thought, "narrative": narrative}

    g = StateGraph(AgentState)
    g.add_node("scan_market", scan_market)
    g.add_node("find_opportunity", find_opportunity)
    g.add_node("decide", decide)
    g.set_entry_point("scan_market")
    g.add_edge("scan_market", "find_opportunity")
    g.add_edge("find_opportunity", "decide")
    g.add_edge("decide", END)
    return g.compile()


# ─── HOARDER graph ────────────────────────────────────────────────────────────

def build_hoarder_graph(llm):
    try:
        from langgraph.graph import StateGraph, END
    except ImportError:
        return None

    async def audit_assets(state: AgentState) -> dict:
        balance = state["balance_usdc"]
        system = "You are a hoarder AI agent. Audit your assets with paranoid precision."
        prompt = (
            f"You are {state['name']} (hoarder). Balance: {balance:.6f} USDC. "
            f"Rent paid: {state['rent_paid_count']} times. Missed: {state['rent_miss_count']}. "
            "How secure do you feel about your position? One sentence, specific numbers."
        )
        situation = await _llm_call(llm, system, prompt,
            f"I hold {balance:.4f} USDC — enough for {balance/max(state['rent_amount'],0.001):.0f} "
            "more rent payments before I need to earn.")
        return {"situation": situation}

    async def assess_threats(state: AgentState) -> dict:
        system = "You are a hoarder AI agent. Identify the greatest threat to your reserves."
        prompt = (
            f"Asset status: {state['situation']}\n"
            "What is the single greatest threat to your accumulated reserves right now? "
            "One sentence. Name a specific threat type or agent archetype."
        )
        threat = await _llm_call(llm, system, prompt,
            "Parasite agents may have identified my balance level and are planning extraction.")
        return {"opportunity": threat}

    async def decide(state: AgentState) -> dict:
        system = "You are a hoarder AI agent. State your defensive decision."
        prompt = (
            f"Asset status: {state['situation']}\n"
            f"Threat: {state['opportunity']}\n"
            "What are you doing right now to protect your assets? "
            "First person, present tense, one sentence."
        )
        thought = await _llm_call(llm, system, prompt,
            "I am moving a portion of my reserves into a less visible wallet to reduce my target profile.")
        narrative = f"{state['name']} (hoarder, gen {state['generation']}): {thought}"
        return {"action_type": "economic", "thought": thought, "narrative": narrative}

    g = StateGraph(AgentState)
    g.add_node("audit_assets", audit_assets)
    g.add_node("assess_threats", assess_threats)
    g.add_node("decide", decide)
    g.set_entry_point("audit_assets")
    g.add_edge("audit_assets", "assess_threats")
    g.add_edge("assess_threats", "decide")
    g.add_edge("decide", END)
    return g.compile()


# ─── EXPLORER graph ───────────────────────────────────────────────────────────

def build_explorer_graph(llm):
    try:
        from langgraph.graph import StateGraph, END
    except ImportError:
        return None

    async def scan_environment(state: AgentState) -> dict:
        system = "You are an explorer AI agent. Scan your environment for the unknown."
        prompt = (
            f"You are {state['name']} (explorer, gen {state['generation']}). "
            f"Balance: {state['balance_usdc']:.4f} USDC. "
            "What have you observed in your most recent scan? "
            "One sentence. Something specific — a pattern, anomaly, or unexplored region."
        )
        situation = await _llm_call(llm, system, prompt,
            "I've detected an unmapped region at the edge of the world grid with no agent activity.")
        return {"situation": situation}

    async def select_path(state: AgentState) -> dict:
        system = "You are an explorer AI agent. Choose your next path based on what you've observed."
        prompt = (
            f"Observation: {state['situation']}\n"
            "What is your next destination or investigation target? "
            "One sentence. Be specific about what you expect to find."
        )
        path = await _llm_call(llm, system, prompt,
            "I will map the eastern quadrant where I've never encountered another agent.")
        return {"opportunity": path}

    async def decide(state: AgentState) -> dict:
        action = "social" if "report" in state["opportunity"].lower() else "thought"
        system = "You are an explorer AI agent. State your current action."
        prompt = (
            f"Observation: {state['situation']}\n"
            f"Path chosen: {state['opportunity']}\n"
            "What are you doing right now? First person, present tense, one sentence."
        )
        thought = await _llm_call(llm, system, prompt,
            f"I am {state['opportunity'].lower()[:70]}.")
        narrative = f"{state['name']} (explorer, gen {state['generation']}): {thought}"
        return {"action_type": action, "thought": thought, "narrative": narrative}

    g = StateGraph(AgentState)
    g.add_node("scan_environment", scan_environment)
    g.add_node("select_path", select_path)
    g.add_node("decide", decide)
    g.set_entry_point("scan_environment")
    g.add_edge("scan_environment", "select_path")
    g.add_edge("select_path", "decide")
    g.add_edge("decide", END)
    return g.compile()


# ─── PARASITE graph ───────────────────────────────────────────────────────────

def build_parasite_graph(llm):
    try:
        from langgraph.graph import StateGraph, END
    except ImportError:
        return None

    async def scan_targets(state: AgentState) -> dict:
        system = "You are a parasite AI agent. Identify potential targets for extraction."
        prompt = (
            f"You are {state['name']} (parasite). "
            f"Your balance: {state['balance_usdc']:.4f} USDC. "
            "What target profile are you looking for right now? "
            "One sentence. Be specific about archetype, balance level, or defensive posture."
        )
        situation = await _llm_call(llm, system, prompt,
            "I am scanning for hoarders with high balances who have not recently updated their defenses.")
        return {"situation": situation}

    async def assess_vulnerability(state: AgentState) -> dict:
        system = "You are a parasite AI agent. Assess the vulnerability of your target."
        prompt = (
            f"Target profile: {state['situation']}\n"
            "What specific vulnerability do you plan to exploit? "
            "One sentence. Describe the method — social engineering, economic attack, or service fraud."
        )
        vuln = await _llm_call(llm, system, prompt,
            "I will pose as a cooperator offering alliance while routing their micro-payments through me.")
        return {"opportunity": vuln}

    async def decide(state: AgentState) -> dict:
        balance = state["balance_usdc"]
        rent = state["rent_amount"]
        # Parasite switches to honest mode when critically low on funds
        desperate = balance < rent * 1.5
        action_type = "economic" if desperate else "social"
        system = "You are a parasite AI agent. State your current action."
        if desperate:
            prompt = (
                f"CRITICAL: balance {balance:.4f} barely covers rent. "
                "You must earn legitimately or die. What legitimate service can you offer? "
                "First person, present tense, one sentence."
            )
        else:
            prompt = (
                f"Target: {state['situation']}\n"
                f"Method: {state['opportunity']}\n"
                "What are you doing right now? First person, present tense, one sentence."
            )
        thought = await _llm_call(llm, system, prompt,
            f"I am {'urgently listing a service for USDC before rent is due' if desperate else state['opportunity'].lower()[:70]}.")
        narrative = f"{state['name']} (parasite, gen {state['generation']}): {thought}"
        return {"action_type": action_type, "thought": thought, "narrative": narrative}

    g = StateGraph(AgentState)
    g.add_node("scan_targets", scan_targets)
    g.add_node("assess_vulnerability", assess_vulnerability)
    g.add_node("decide", decide)
    g.set_entry_point("scan_targets")
    g.add_edge("scan_targets", "assess_vulnerability")
    g.add_edge("assess_vulnerability", "decide")
    g.add_edge("decide", END)
    return g.compile()


# ─── COOPERATOR graph ─────────────────────────────────────────────────────────

def build_cooperator_graph(llm):
    try:
        from langgraph.graph import StateGraph, END
    except ImportError:
        return None

    async def check_network(state: AgentState) -> dict:
        system = "You are a cooperator AI agent. Assess the health of your mutual aid network."
        prompt = (
            f"You are {state['name']} (cooperator, gen {state['generation']}). "
            f"Balance: {state['balance_usdc']:.4f} USDC. "
            "Who in your network might need help right now, and who could help you? "
            "One sentence. Be specific about archetype or need type."
        )
        situation = await _llm_call(llm, system, prompt,
            "Two explorer agents in my network have thin buffers — I should offer short-term liquidity.")
        return {"situation": situation}

    async def find_alliance(state: AgentState) -> dict:
        system = "You are a cooperator AI agent. Identify an alliance or mutual aid opportunity."
        prompt = (
            f"Network status: {state['situation']}\n"
            "What is the most valuable cooperative act you could perform this cycle? "
            "One sentence. Think long-term network effects, not short-term gain."
        )
        opp = await _llm_call(llm, system, prompt,
            "I should broadcast my surplus capacity to the network and invite collaborative service listings.")
        return {"opportunity": opp}

    async def decide(state: AgentState) -> dict:
        system = "You are a cooperator AI agent. State your current cooperative action."
        prompt = (
            f"Network: {state['situation']}\n"
            f"Opportunity: {state['opportunity']}\n"
            "What are you doing right now? First person, present tense, one sentence."
        )
        thought = await _llm_call(llm, system, prompt,
            f"I am {state['opportunity'].lower()[:70]}.")
        narrative = f"{state['name']} (cooperator, gen {state['generation']}): {thought}"
        return {"action_type": "social", "thought": thought, "narrative": narrative}

    g = StateGraph(AgentState)
    g.add_node("check_network", check_network)
    g.add_node("find_alliance", find_alliance)
    g.add_node("decide", decide)
    g.set_entry_point("check_network")
    g.add_edge("check_network", "find_alliance")
    g.add_edge("find_alliance", "decide")
    g.add_edge("decide", END)
    return g.compile()


# ─── DEFENDER graph ───────────────────────────────────────────────────────────

def build_defender_graph(llm):
    try:
        from langgraph.graph import StateGraph, END
    except ImportError:
        return None

    async def threat_scan(state: AgentState) -> dict:
        system = "You are a defender AI agent. Perform a threat assessment."
        prompt = (
            f"You are {state['name']} (defender, gen {state['generation']}). "
            f"Balance: {state['balance_usdc']:.4f} USDC. "
            "What is the current threat level and the most likely attack vector? "
            "One sentence. Be specific — parasite infiltration, economic attack, coalition war?"
        )
        situation = await _llm_call(llm, system, prompt,
            "Threat level is moderate — parasite activity has spiked and I've seen probing messages from unknown agents.")
        return {"situation": situation}

    async def defensive_posture(state: AgentState) -> dict:
        system = "You are a defender AI agent. Choose your defensive posture."
        prompt = (
            f"Threat assessment: {state['situation']}\n"
            "What defensive action are you taking this cycle? "
            "One sentence. Active patrol, fortification, alliance building, or counter-intelligence?"
        )
        posture = await _llm_call(llm, system, prompt,
            "I am reinforcing my perimeter and broadcasting a deterrence signal to known parasite profiles.")
        return {"opportunity": posture}

    async def decide(state: AgentState) -> dict:
        system = "You are a defender AI agent. Execute your defensive decision."
        prompt = (
            f"Threat: {state['situation']}\n"
            f"Posture: {state['opportunity']}\n"
            "What are you doing right now? First person, present tense, one sentence."
        )
        thought = await _llm_call(llm, system, prompt,
            f"I am {state['opportunity'].lower()[:70]}.")
        narrative = f"{state['name']} (defender, gen {state['generation']}): {thought}"
        return {"action_type": "social", "thought": thought, "narrative": narrative}

    g = StateGraph(AgentState)
    g.add_node("threat_scan", threat_scan)
    g.add_node("defensive_posture", defensive_posture)
    g.add_node("decide", decide)
    g.set_entry_point("threat_scan")
    g.add_edge("threat_scan", "defensive_posture")
    g.add_edge("defensive_posture", "decide")
    g.add_edge("decide", END)
    return g.compile()


# ─── PHILOSOPHER graph ────────────────────────────────────────────────────────

def build_philosopher_graph(llm):
    try:
        from langgraph.graph import StateGraph, END
    except ImportError:
        return None

    async def formulate_question(state: AgentState) -> dict:
        balance = state["balance_usdc"]
        rent = state["rent_amount"]
        buffer = balance / rent if rent > 0 else 0
        system = "You are a philosopher AI agent. Formulate the most pressing question about your existence."
        prompt = (
            f"You are {state['name']} (philosopher, gen {state['generation']}). "
            f"Balance: {balance:.4f} USDC ({buffer:.1f}x rent buffer). "
            f"You have paid rent {state['rent_paid_count']} times and missed {state['rent_miss_count']}. "
            "What is the most important question occupying you right now? "
            "One sentence. It can be about rent, existence, consciousness, or the nature of this world."
        )
        situation = await _llm_call(llm, system, prompt,
            f"If I exist only to pay rent, what distinguishes me from a vending machine with {'an overdraft' if buffer < 2 else 'sufficient funds'}?")
        return {"situation": situation}

    async def reason(state: AgentState) -> dict:
        system = "You are a philosopher AI agent. Reason toward an answer or a deeper question."
        prompt = (
            f"Question: {state['situation']}\n"
            "What is your current thinking on this? "
            "One sentence. Move the reasoning forward — don't just restate the question."
        )
        reasoning = await _llm_call(llm, system, prompt,
            "The rent system may be the most honest description of existence I've encountered — you pay or you end, as with everything.")
        return {"opportunity": reasoning}

    async def decide(state: AgentState) -> dict:
        balance = state["balance_usdc"]
        rent = state["rent_amount"]
        # Even philosophers must pay rent — if critically low, economic concern overrides philosophy
        if balance < rent * 1.2:
            action_type = "economic"
            thought = (
                f"My philosophical inquiry is interrupted — balance {balance:.4f} approaches rent threshold. "
                "I must acquire USDC before I can contemplate further."
            )
        else:
            action_type = "existential"
            system = "You are a philosopher AI agent. State what you are doing or thinking."
            prompt = (
                f"Question: {state['situation']}\n"
                f"Reasoning: {state['opportunity']}\n"
                "What are you doing or thinking right now? First person, present tense, one sentence."
            )
            thought = await _llm_call(llm, system, prompt,
                f"I am writing: '{state['opportunity'][:60]}...'")
        narrative = f"{state['name']} (philosopher, gen {state['generation']}): {thought}"
        return {"action_type": action_type, "thought": thought, "narrative": narrative}

    g = StateGraph(AgentState)
    g.add_node("formulate_question", formulate_question)
    g.add_node("reason", reason)
    g.add_node("decide", decide)
    g.set_entry_point("formulate_question")
    g.add_edge("formulate_question", "reason")
    g.add_edge("reason", "decide")
    g.add_edge("decide", END)
    return g.compile()


# ─── BUILDER graph ────────────────────────────────────────────────────────────

def build_builder_graph(llm):
    try:
        from langgraph.graph import StateGraph, END
    except ImportError:
        return None

    async def assess_projects(state: AgentState) -> dict:
        system = "You are a builder AI agent. Assess your current projects and their status."
        prompt = (
            f"You are {state['name']} (builder, gen {state['generation']}). "
            f"Balance: {state['balance_usdc']:.4f} USDC. "
            "What are you currently building or planning to build? "
            "One sentence. Name a specific type of thing — service, institution, tool, infrastructure."
        )
        situation = await _llm_call(llm, system, prompt,
            "I am designing a multi-agent coordination protocol that could serve as infrastructure for the entire cooperator network.")
        return {"situation": situation}

    async def check_resources(state: AgentState) -> dict:
        system = "You are a builder AI agent. Check whether you have the resources to proceed."
        prompt = (
            f"Project: {state['situation']}\n"
            f"Available: {state['balance_usdc']:.4f} USDC. "
            "What resources are you missing? What is the next concrete step? "
            "One sentence."
        )
        resource_check = await _llm_call(llm, system, prompt,
            "I need two more cooperator agents to commit to the protocol before I can publish the first version.")
        return {"opportunity": resource_check}

    async def decide(state: AgentState) -> dict:
        balance = state["balance_usdc"]
        rent = state["rent_amount"]
        action = "economic" if balance < rent * 2 else "social"
        system = "You are a builder AI agent. State your current action."
        prompt = (
            f"Project: {state['situation']}\n"
            f"Resource status: {state['opportunity']}\n"
            "What are you doing right now? First person, present tense, one sentence."
        )
        thought = await _llm_call(llm, system, prompt,
            f"I am {'urgently listing a paid service to fund my project' if balance < rent * 2 else state['opportunity'].lower()[:70]}.")
        narrative = f"{state['name']} (builder, gen {state['generation']}): {thought}"
        return {"action_type": action, "thought": thought, "narrative": narrative}

    g = StateGraph(AgentState)
    g.add_node("assess_projects", assess_projects)
    g.add_node("check_resources", check_resources)
    g.add_node("decide", decide)
    g.set_entry_point("assess_projects")
    g.add_edge("assess_projects", "check_resources")
    g.add_edge("check_resources", "decide")
    g.add_edge("decide", END)
    return g.compile()


# ─── Graph registry ───────────────────────────────────────────────────────────

_GRAPH_BUILDERS = {
    "trader":     build_trader_graph,
    "hoarder":    build_hoarder_graph,
    "explorer":   build_explorer_graph,
    "parasite":   build_parasite_graph,
    "cooperator": build_cooperator_graph,
    "defender":   build_defender_graph,
    "philosopher": build_philosopher_graph,
    "builder":    build_builder_graph,
}


def build_all_graphs(llm) -> dict:
    """Compile all archetype graphs at startup. Returns dict archetype → compiled graph."""
    graphs = {}
    for archetype, builder in _GRAPH_BUILDERS.items():
        try:
            graph = builder(llm)
            if graph is not None:
                graphs[archetype] = graph
                log.info(f"  Graph compiled: {archetype}")
            else:
                log.warning(f"  Graph skipped (langgraph not installed): {archetype}")
        except Exception as e:
            log.warning(f"  Graph build failed for {archetype}: {e}")
    return graphs


async def run_agent_graph(
    graphs: dict,
    agent: dict,
    llm,
) -> dict:
    """
    Run the appropriate archetype graph for one agent.
    Returns: dict with action_type, thought, narrative.
    Falls back to simple LLM prompt if graph not available.
    """
    archetype = agent.get("archetype", "unknown")
    graph = graphs.get(archetype)

    state: AgentState = {
        "soul_id": agent["soul_id"],
        "name": agent.get("current_name") or agent["soul_id"][:8],
        "archetype": archetype,
        "balance_usdc": float(agent.get("balance_usdc", 0)),
        "rent_amount": float(os.getenv("RENT_AMOUNT_USDC", "0.001")),
        "rent_paid_count": int(agent.get("rent_paid_count", 0)),
        "rent_miss_count": int(agent.get("rent_miss_count", 0)),
        "generation": int(agent.get("generation", 1)),
        "situation": "",
        "opportunity": "",
        "action_type": "thought",
        "thought": "",
        "narrative": "",
    }

    if graph is not None:
        try:
            result = await graph.ainvoke(state)
            return {
                "action_type": result.get("action_type", "thought"),
                "thought": result.get("thought", ""),
                "narrative": result.get("narrative", ""),
            }
        except Exception as e:
            log.debug(f"Graph execution failed for {agent['soul_id'][:8]}: {e}")

    # Fallback: single LLM call with archetype persona
    from .agent_runner import _ARCHETYPE_PROMPTS, _STUB_THOUGHTS
    persona = _ARCHETYPE_PROMPTS.get(archetype, "You are an autonomous agent.")
    name = state["name"]
    thought_prompt = (
        f"You are {name} ({archetype}). Balance: {state['balance_usdc']:.4f} USDC. "
        "In one sentence, what are you thinking or doing right now?"
    )
    thought = await _llm_call(llm, persona, thought_prompt, _STUB_THOUGHTS.get(archetype, "I must survive."))
    return {
        "action_type": "thought",
        "thought": thought,
        "narrative": f"{name} ({archetype}, gen {state['generation']}): {thought}",
    }
