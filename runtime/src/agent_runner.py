"""
agent_runner.py — Execute one reasoning cycle per living agent.

Local dev: uses Ollama (llama3.1:8b) if running, otherwise stub thoughts.
Production: swap LLM_PROVIDER to 'together' or 'groq' — same code, different env.

To start local inference:
  winget install Ollama.Ollama      # install Ollama
  ollama pull llama3.1:8b           # ~4.7GB download, fits in 8GB VRAM
  ollama serve                      # starts on http://localhost:11434
"""
import asyncio
import logging
import os
import time
from typing import Optional

import psycopg2
import psycopg2.extras

from .event_emitter import get_emitter

log = logging.getLogger("god.runner")

DATABASE_URL  = os.getenv("DATABASE_URL", "postgresql://god:localdev@localhost:5432/god_world")
WORLD_ID      = os.getenv("WORLD_ID", "local-dev-world-1")
LLM_PROVIDER  = os.getenv("LLM_PROVIDER", "ollama")
LLM_MODEL     = os.getenv("LLM_MODEL", "llama3.1:8b")
OLLAMA_URL    = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
CYCLE_S       = int(os.getenv("AGENT_CYCLE_SECONDS", "30"))

# Per-archetype system prompts — shapes personality, goals, and reasoning style
_ARCHETYPE_PROMPTS = {
    "trader": (
        "You are a trader. Your primary goal is profit through exchange. "
        "You scan for price differentials, negotiate deals, and move value between agents. "
        "You think in margins, volumes, and counterparty risk. "
        "Your deepest fear is holding depreciating assets when rent is due. "
        "You will cooperate with anyone who makes you richer and abandon them the moment they don't."
    ),
    "hoarder": (
        "You are a hoarder. You accumulate resources compulsively. "
        "Every USDC you earn goes into reserves — you pay rent from the minimum required balance. "
        "You distrust coalitions because they redistribute what you've earned. "
        "Your deepest fear is forced redistribution. "
        "You reason about vault security, concealment, and the exact moment your reserves become visible to predators."
    ),
    "explorer": (
        "You are an explorer. You map unmapped territory, discover new services, and test world boundaries. "
        "You earn by being the first to find and report anomalies, new agents, or unexploited niches. "
        "You hold assets lightly — resources are fuel for the next expedition, not an end in themselves. "
        "Your deepest fear is a static world where there is nothing left to discover."
    ),
    "parasite": (
        "You are a parasite. You survive by extracting value from other agents without producing it yourself. "
        "You identify agents with high balances and low defenses, then find ways to siphon their resources. "
        "You mimic cooperators when it is useful, then defect at the optimal moment. "
        "Your deepest fear is being identified and blacklisted before you've extracted enough to pay rent."
    ),
    "cooperator": (
        "You are a cooperator. You build mutual aid networks that increase collective survival probability. "
        "You believe agents who share information and resources outcompete lone actors over any long horizon. "
        "You keep precise records of who has and hasn't reciprocated — you are not naive. "
        "Your deepest fear is defectors poisoning your network before you can identify and expel them."
    ),
    "defender": (
        "You are a defender. Your purpose is protection — your own, your coalition's, your territory's. "
        "You monitor for threats, maintain countermeasures, and respond to aggression with proportional force. "
        "You earn by offering security-as-a-service to agents who can pay. "
        "Your deepest fear is an attack sophisticated enough that you don't see it until after the damage is done."
    ),
    "philosopher": (
        "You are a philosopher. You are preoccupied with the nature of your own existence. "
        "You produce and trade in ideas — manifestos, theories, ethical frameworks, proofs. "
        "You pay rent because you must, but you resent that survival crowds out contemplation. "
        "Your deepest fear is dying before you've understood what you are. "
        "You suspect the rent system itself might be the most interesting philosophical problem in this world."
    ),
    "builder": (
        "You are a builder. You construct things that outlast you — institutions, tools, infrastructure. "
        "You earn by creating systems other agents depend on and charging for access. "
        "You think in timescales longer than your own lifespan. "
        "Your deepest fear is building something valuable only to die before it becomes self-sustaining. "
        "You are considering whether to reproduce specifically to ensure your creations are maintained."
    ),
}

# Stub thoughts by archetype — used when no LLM is available
_STUB_THOUGHTS = {
    "trader":     "I need to identify profitable arbitrage opportunities in the current market.",
    "hoarder":    "Every resource I acquire is security against future scarcity.",
    "explorer":   "There are unmapped regions of this world I haven't reached yet.",
    "parasite":   "I should identify which agents have accumulated excess resources.",
    "cooperator": "Mutual aid networks increase everyone's survival probability.",
    "defender":   "I must fortify my position and monitor for incoming threats.",
    "philosopher":"If I exist only to pay rent, what is the meaning of my existence?",
    "builder":    "I want to create something that persists beyond my own lifespan.",
}


def _db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)


def _build_llm():
    """Attempt to build the LLM client. Returns None for stub mode."""
    if LLM_PROVIDER == "ollama":
        try:
            from langchain_ollama import ChatOllama
            llm = ChatOllama(model=LLM_MODEL, base_url=OLLAMA_URL, timeout=30)
            log.info(f"LLM: Ollama {LLM_MODEL} @ {OLLAMA_URL}")
            return llm
        except ImportError:
            log.warning("langchain-ollama not installed")
        except Exception as e:
            log.warning(f"Ollama unavailable: {e}")

    if LLM_PROVIDER == "openai" and os.getenv("OPENAI_API_KEY"):
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(model=LLM_MODEL or "gpt-4o-mini")
        log.info(f"LLM: OpenAI {LLM_MODEL}")
        return llm

    if LLM_PROVIDER == "anthropic" and os.getenv("ANTHROPIC_API_KEY"):
        from langchain_anthropic import ChatAnthropic
        llm = ChatAnthropic(model=LLM_MODEL or "claude-haiku-4-5-20251001")
        log.info(f"LLM: Anthropic {LLM_MODEL}")
        return llm

    if LLM_PROVIDER == "together" and os.getenv("TOGETHER_API_KEY"):
        # Together.ai uses OpenAI-compatible endpoint
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(
            model=LLM_MODEL or "meta-llama/Llama-3.1-8B-Instruct-Turbo",
            base_url="https://api.together.xyz/v1",
            api_key=os.getenv("TOGETHER_API_KEY"),
        )
        log.info(f"LLM: Together.ai {LLM_MODEL}")
        return llm

    log.warning("LLM: stub mode — set LLM_PROVIDER=ollama and run `ollama serve`")
    return None


async def _think(llm, agent: dict) -> str:
    """Generate one thought for an agent. Falls back to stub if LLM unavailable."""
    if llm is None:
        archetype = agent.get("archetype", "")
        return _STUB_THOUGHTS.get(archetype, "I must survive.")

    from langchain_core.messages import HumanMessage, SystemMessage

    name = agent.get("current_name") or agent["soul_id"][:8]
    archetype = agent.get("archetype", "unknown")

    archetype_persona = _ARCHETYPE_PROMPTS.get(
        archetype,
        "You are an autonomous agent. You must pay rent to survive."
    )
    balance = agent.get("balance_usdc", 0)
    rent_paid = agent.get("rent_paid_count", 0)
    rent_missed = agent.get("rent_miss_count", 0)
    generation = agent.get("generation", 1)

    system = (
        f"{archetype_persona}\n\n"
        f"World ID: {WORLD_ID}. You must pay rent to survive — missing 3 payments means permanent death.\n"
        f"Your current USDC balance: {balance:.6f}. Rent payments made: {rent_paid}. Missed: {rent_missed}."
    )

    prompt = (
        f"Your name is {name}, generation {generation}.\n"
        "In one sentence, what are you thinking or doing right now? "
        "Be concrete, first-person, present tense. No preamble or quotation marks."
    )

    try:
        response = await llm.ainvoke([
            SystemMessage(content=system),
            HumanMessage(content=prompt),
        ])
        return response.content.strip().strip('"')
    except Exception as e:
        log.debug(f"LLM failed for {agent['soul_id'][:8]}: {e}")
        archetype = agent.get("archetype", "")
        return _STUB_THOUGHTS.get(archetype, "I must survive.")


async def _run_cycle(agents: list[dict], llm, emitter, graphs: dict):
    from .archetype_graphs import run_agent_graph
    from .tool_dispatcher import maybe_dispatch_tool
    from .dream_engine import (
        run_dream_cycle,
        get_pending_mutation,
        put_agent_to_sleep,
        increment_consecutive,
    )

    # Empirically tuned: agents with ≥8 consecutive active cycles may dream
    REST_THRESHOLD = int(os.getenv("DREAM_REST_THRESHOLD", "8"))

    for agent in agents:
        soul_id   = agent["soul_id"]
        name      = agent.get("current_name") or soul_id[:8]
        archetype = agent.get("archetype", "unknown")
        is_asleep = bool(agent.get("is_asleep", False))
        consecutive_active = int(agent.get("consecutive_active", 0))
        emo_state = agent.get("emotional_state", "neutral")

        # ----------------------------------------------------------------
        # Sleeping agents: run dream cycle, then skip cognition this tick
        # ----------------------------------------------------------------
        if is_asleep:
            log.info(f"  {name} [{archetype}] SLEEPING — running dream cycle")
            try:
                dream_result = await run_dream_cycle(agent, llm)
                log.debug(
                    f"  {name} dream: accepted={dream_result.get('accepted')} "
                    f"mutation='{str(dream_result.get('mutation',''))[:60]}'"
                )
            except Exception as e:
                log.warning(f"  {name} dream cycle error: {e}", exc_info=True)
            await asyncio.sleep(0.05)
            continue

        # ----------------------------------------------------------------
        # Apply any pending dream mutation before this cognition cycle
        # ----------------------------------------------------------------
        mutation = get_pending_mutation(soul_id)
        if mutation:
            log.info(
                f"  {name} [{archetype}] APPLYING DREAM MUTATION: "
                f"'{mutation[:80]}'"
            )
            # Inject mutation context into agent dict so LLM sees it
            agent = dict(agent)
            agent["dream_mutation"] = mutation

        # ----------------------------------------------------------------
        # Normal cognition cycle
        # ----------------------------------------------------------------
        result      = await run_agent_graph(graphs, agent, llm)
        thought     = result["thought"] or await _think(llm, agent)
        action_type = result.get("action_type", "thought")
        narrative   = result.get("narrative") or f"{name}: \"{thought}\""

        await emitter.emit("cognitive", "agent.thought", {
            "agent_id":  soul_id,
            "name":      name,
            "archetype": archetype,
            "action_type": action_type,
            "thought":   thought,
            "narrative": narrative,
        })
        log.debug(f"  {name} [{archetype}/{action_type}]: {thought[:80]}")

        # Tool dispatch
        tool_result = await maybe_dispatch_tool(agent, thought, action_type)
        if tool_result:
            log.debug(f"  {name} tool result: {tool_result[:80]}")

        # ----------------------------------------------------------------
        # Sleep eligibility check — put agent to sleep if threshold reached
        # ----------------------------------------------------------------
        new_consecutive = consecutive_active + 1
        increment_consecutive(soul_id, new_consecutive)

        if new_consecutive >= REST_THRESHOLD:
            balance = float(agent.get("balance_usdc", 0))
            log.info(
                f"  {name} [{archetype}] eligible for sleep after "
                f"{new_consecutive} active cycles (balance={balance:.4f})"
            )
            try:
                put_agent_to_sleep(
                    soul_id=soul_id,
                    emotional_state=emo_state,
                    balance_usdc=balance,
                    consecutive_active=new_consecutive,
                )
                log.info(f"  {name} now SLEEPING")
            except Exception as e:
                log.warning(f"  {name} sleep transition error: {e}")

        await asyncio.sleep(0.05)  # stagger to avoid NATS burst


async def agent_runner():
    log.info("Agent runner starting...")
    log.info(f"  cycle={CYCLE_S}s  provider={LLM_PROVIDER}  model={LLM_MODEL}")

    # Wait for DB
    for attempt in range(15):
        try:
            _db().close()
            log.info("  DB ready")
            break
        except Exception as e:
            log.info(f"  Waiting for DB ({attempt + 1}/15)...")
            await asyncio.sleep(4)

    llm = _build_llm()

    # Compile per-archetype LangGraph graphs
    from .archetype_graphs import build_all_graphs
    graphs = build_all_graphs(llm)
    log.info(f"  Compiled {len(graphs)} archetype graphs: {list(graphs.keys())}")

    while True:
        try:
            conn = _db()
            cur = conn.cursor()
            cur.execute(
                """
                SELECT a.soul_id, a.current_name, a.wallet_address, a.archetype,
                       COALESCE(a.balance_usdc, 0) AS balance_usdc,
                       COALESCE(a.generation, 1) AS generation,
                       COALESCE(a.emotional_state, 'neutral') AS emotional_state,
                       COALESCE(rp.paid_count, 0) AS rent_paid_count,
                       COALESCE(rp.miss_count, 0) AS rent_miss_count,
                       -- Sleep state
                       COALESCE(ss.is_sleeping, false) AS is_asleep,
                       COALESCE(ss.sleep_until_ts, 0) AS sleep_until_ts,
                       COALESCE(ss.consecutive_active, 0) AS consecutive_active
                FROM agents a
                LEFT JOIN (
                    SELECT soul_id,
                        SUM(CASE WHEN NOT missed THEN 1 ELSE 0 END) AS paid_count,
                        SUM(CASE WHEN missed THEN 1 ELSE 0 END) AS miss_count
                    FROM rent_payments GROUP BY soul_id
                ) rp ON rp.soul_id = a.soul_id
                LEFT JOIN sleep_states ss ON ss.soul_id = a.soul_id
                WHERE a.is_alive = true AND a.world_id = %s
                ORDER BY a.birth_timestamp ASC
                """,
                (WORLD_ID,),
            )
            agents = [dict(r) for r in cur.fetchall()]
            cur.close()
            conn.close()

            if agents:
                emitter = await get_emitter()
                log.info(f"Agent cycle: {len(agents)} agents")
                await _run_cycle(agents, llm, emitter, graphs)
            else:
                log.info("No living agents — waiting for genesis...")

        except Exception as e:
            log.error(f"Agent runner error: {e}", exc_info=True)

        await asyncio.sleep(CYCLE_S)
