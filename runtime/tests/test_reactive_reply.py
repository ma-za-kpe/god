"""Reactive reply lane tests."""

import asyncio

import archetype_graphs as ag
from archetype_graphs import run_reactive_reply


def test_reactive_reply_builds_a_direct_response():
    agent = {
        "soul_id": "s-alpha",
        "current_name": "Alpha",
        "archetype": "philosopher",
        "balance_usdc": 0.125,
        "generation": 3,
        "_peers": [
            {
                "soul_id": "s-beta",
                "current_name": "Beta",
                "archetype": "defender",
                "balance_usdc": 0.22,
            },
        ],
        "_inbox": [
            {
                "message_id": "msg-1",
                "sender_id": "s-beta",
                "sender_name": "Beta",
                "sender_archetype": "defender",
                "recipient_id": "s-alpha",
                "content": "You keep avoiding the question.",
            }
        ],
        "_conv_thread": [],
        "_recent_sent": [],
        "_my_services": [],
        "_market_services": [],
        "_my_coalitions": [],
        "_world_coalitions": [],
        "_reputation_avg": 0.0,
        "_pending_wake_intents": [],
        "arc_theme": "Should the weak be protected?",
    }

    async def fake_llm_call(_llm, _system, _prompt, _fallback, state=None):
        return (
            '{"thought":"I answer Beta directly.","move":"COUNTER","action":"send_message",'
            '"to_id":"Beta","content":"You are dodging the real issue: who benefits when the weak are abandoned?",'
            '"message_type":"direct","reply_to_id":"msg-1"}'
        )

    original = ag._llm_call
    ag._llm_call = fake_llm_call
    try:
        result = asyncio.run(run_reactive_reply(agent, object()))
    finally:
        ag._llm_call = original

    assert result["action_type"] == "social"
    assert result["thought"]
    assert result["action"]["type"] == "send_message"
    assert result["action"]["to_id"] == "s-beta"
    assert result["action"]["reply_to_id"] == "msg-1"
    assert (
        result["action"]["content"]
        == "You are dodging the real issue: who benefits when the weak are abandoned?"
    )
    assert result["thought"] == result["action"]["content"]


def test_reactive_reply_rejects_repetitive_model_content():
    agent = {
        "soul_id": "s-alpha",
        "current_name": "Alpha",
        "archetype": "cooperator",
        "balance_usdc": 0.125,
        "generation": 3,
        "_peers": [
            {
                "soul_id": "s-beta",
                "current_name": "Beta",
                "archetype": "defender",
                "balance_usdc": 0.22,
            },
        ],
        "_inbox": [
            {
                "message_id": "msg-2",
                "sender_id": "s-beta",
                "sender_name": "Beta",
                "sender_archetype": "defender",
                "recipient_id": "s-alpha",
                "content": "You are dodging the room.",
            }
        ],
        "_conv_thread": [],
        "_recent_sent": [],
        "_my_services": [],
        "_market_services": [],
        "_my_coalitions": [],
        "_world_coalitions": [],
        "_reputation_avg": 0.0,
        "_pending_wake_intents": [],
        "arc_theme": "Should the weak be protected?",
    }

    async def fake_llm_call(_llm, _system, _prompt, _fallback, state=None):
        return (
            '{"thought":"Useful. Useful. Only if the room changes.","move":"QUESTION",'
            '"action":"send_message","to_id":"Beta",'
            '"content":"Useful. Useful. Only if the room changes.","message_type":"direct",'
            '"reply_to_id":"msg-2"}'
        )

    original = ag._llm_call
    ag._llm_call = fake_llm_call
    try:
        result = asyncio.run(run_reactive_reply(agent, object()))
    finally:
        ag._llm_call = original

    assert result["action"]["content"]
    assert "useful. useful." not in result["action"]["content"].lower()
    assert result["action"]["content"] != result["thought"] or result["thought"]


def test_reactive_banter_fallback_uses_callback_and_cadence():
    line, profile = ag._compose_reactive_banter(
        "Beta",
        "philosopher",
        "You keep avoiding the question.",
        "Should the weak be protected?",
        "QUESTION",
        conv_thread=[
            {"direction": "received", "content": "You keep avoiding the question."},
            {
                "direction": "sent",
                "content": "Maybe the weak are only weak because we keep calling them that.",
            },
        ],
        recent_sent=[
            {
                "recipient_name": "Beta",
                "content": "Maybe the weak are only weak because we keep calling them that.",
            }
        ],
    )

    assert line
    assert "said:" not in line.lower()
    assert "theme:" not in line.lower()
    assert profile["cadence"] in {"short", "medium", "build", "callback"}
    assert "question" in line.lower() or "weak" in line.lower()


def test_reactive_polish_collapses_repeated_openers():
    cleaned = ag._polish_reactive_text("Useful. Useful. Only if the room changes.", max_len=120)

    assert cleaned.lower().startswith("useful")
    assert "useful. useful." not in cleaned.lower()


def test_banter_loop_guidelines_include_the_added_standard():
    guideline_text = "\n".join(ag._BANTER_LOOP_GUIDELINES)

    assert "Pure snark gets old" in guideline_text
    assert "ma-za-kpe ecology" in guideline_text
    assert "the Veil, the Swarm, chat, and patron gods" in guideline_text
    assert "ancient cosmic beings" in guideline_text


def test_reactive_prompt_repeats_banter_loop_standard():
    captured = {}
    agent = {
        "soul_id": "s-alpha",
        "current_name": "Alpha",
        "archetype": "cooperator",
        "balance_usdc": 0.125,
        "generation": 3,
        "_peers": [
            {
                "soul_id": "s-beta",
                "current_name": "Beta",
                "archetype": "hoarder",
                "balance_usdc": 0.22,
            },
        ],
        "_inbox": [
            {
                "message_id": "msg-loop-standard",
                "sender_id": "s-beta",
                "sender_name": "Beta",
                "sender_archetype": "hoarder",
                "recipient_id": "s-alpha",
                "content": "Sharing sounds noble until loss has a receipt.",
            }
        ],
        "_conv_thread": [],
        "_recent_sent": [],
        "_my_services": [],
        "_market_services": [],
        "_my_coalitions": [],
        "_world_coalitions": [],
        "_reputation_avg": 0.0,
        "_pending_wake_intents": [],
        "arc_theme": "Patronage as Divine Intervention in a Scarcity Economy",
    }

    async def fake_llm_call(_llm, _system, prompt, fallback, state=None):
        captured["prompt"] = prompt
        return fallback

    original = ag._llm_call
    ag._llm_call = fake_llm_call
    try:
        asyncio.run(run_reactive_reply(agent, object()))
    finally:
        ag._llm_call = original

    prompt = captured["prompt"]
    assert "BANTER LOOP CHECK (repeat every reply until it becomes instinct):" in prompt
    assert "- Pure snark gets old" in prompt
    assert "ma-za-kpe ecology" in prompt
    assert "ancient cosmic beings" in prompt


def test_reactive_prompt_includes_relationship_snapshot():
    captured = {}
    agent = {
        "soul_id": "s-alpha",
        "current_name": "Alpha",
        "archetype": "hoarder",
        "balance_usdc": 0.125,
        "generation": 3,
        "_peers": [
            {
                "soul_id": "s-beta",
                "current_name": "Beta",
                "archetype": "cooperator",
                "balance_usdc": 0.22,
            },
        ],
        "_inbox": [
            {
                "message_id": "msg-rel",
                "sender_id": "s-beta",
                "sender_name": "Beta",
                "sender_archetype": "cooperator",
                "recipient_id": "s-alpha",
                "content": "You keep hoarding trust and calling it safety.",
            }
        ],
        "_conv_thread": [
            {"direction": "received", "sender_name": "Beta", "content": "You keep hoarding trust."},
            {
                "direction": "sent",
                "recipient_name": "Beta",
                "content": "Trust without cost is a leak.",
            },
            {
                "direction": "received",
                "sender_name": "Beta",
                "content": "That fear is eating the room.",
            },
            {
                "direction": "sent",
                "recipient_name": "Beta",
                "content": "The room spends what I have to keep.",
            },
        ],
        "_recent_sent": [
            {"recipient_name": "Beta", "content": "Trust without cost is a leak."},
            {"recipient_name": "Beta", "content": "The room spends what I have to keep."},
        ],
        "_my_services": [],
        "_market_services": [],
        "_my_coalitions": [],
        "_world_coalitions": [],
        "_reputation_avg": 0.0,
        "_pending_wake_intents": [],
        "arc_theme": "The Ethics of Hoarding in a Finite World",
    }

    async def fake_llm_call(_llm, _system, prompt, fallback, state=None):
        captured["prompt"] = prompt
        return fallback

    original = ag._llm_call
    ag._llm_call = fake_llm_call
    try:
        asyncio.run(run_reactive_reply(agent, object()))
    finally:
        ag._llm_call = original

    assert "RELATIONSHIP SNAPSHOT:" in captured["prompt"]
    assert "You have pressed Beta 2 times recently" in captured["prompt"]
    assert "change the angle" in captured["prompt"]


def test_reactive_reply_ignores_stale_dead_sender_inbox():
    captured = {}
    agent = {
        "soul_id": "s-alpha",
        "current_name": "Alpha",
        "archetype": "defender",
        "balance_usdc": 0.125,
        "generation": 3,
        "_peers": [
            {
                "soul_id": "s-beta",
                "current_name": "Beta",
                "archetype": "cooperator",
                "balance_usdc": 0.22,
            },
        ],
        "_inbox": [
            {
                "message_id": "msg-dead",
                "sender_id": "s-dead",
                "sender_name": "Ghost",
                "sender_archetype": "hoarder",
                "recipient_id": "s-alpha",
                "content": "Answer an old argument from the grave.",
            }
        ],
        "_conv_thread": [],
        "_recent_sent": [],
        "_my_services": [],
        "_market_services": [],
        "_my_coalitions": [],
        "_world_coalitions": [],
        "_reputation_avg": 0.0,
        "_pending_wake_intents": [],
        "arc_theme": "Scarcity makes every alliance expensive",
    }

    async def fake_llm_call(_llm, _system, prompt, fallback, state=None):
        captured["prompt"] = prompt
        return fallback

    original = ag._llm_call
    ag._llm_call = fake_llm_call
    try:
        result = asyncio.run(run_reactive_reply(agent, object()))
    finally:
        ag._llm_call = original

    assert "There is no live message yet" in captured["prompt"]
    assert "Ghost" not in captured["prompt"]
    assert "START_WITH: Beta [cooperator]" in captured["prompt"]
    assert result["action"]["to_id"] == "s-beta"


def test_banter_loop_scores_up_the_quality_rubric():
    line = ag._banter_loop(
        "Exactly. The room only holds if the room only holds if the room only holds.",
        archetype="cooperator",
        move="QUESTION",
        message_text="You are dodging the room.",
        arc_theme="What Does Cooperation Mean When Trust Cannot Be Verified?",
    )

    score = ag._banter_quality_score(
        line,
        archetype="cooperator",
        move="QUESTION",
        message_text="You are dodging the room.",
        arc_theme="What Does Cooperation Mean When Trust Cannot Be Verified?",
    )

    assert line
    assert score >= 5
    assert "room only holds if the room only holds" not in line.lower()


def test_reactive_banter_avoids_single_word_filler_callbacks():
    line, profile = ag._compose_reactive_banter(
        "Beta",
        "cooperator",
        "You are dodging the room.",
        "What Does Cooperation Mean When Trust Cannot Be Verified?",
        "QUESTION",
    )

    assert line
    assert not line.lower().startswith(("useful ", "maybe "))
    assert profile["backchannel"] in {
        "Exactly.",
        "Useful.",
        "Maybe.",
        "No.",
        "Not for free.",
        "Good. Name the cost.",
        "Show me.",
        "Then build it.",
    }


def test_banter_loop_adds_vulnerability_or_meta_when_needed():
    cooperator = ag._banter_loop(
        "Answer the room.",
        archetype="cooperator",
        move="QUESTION",
        message_text="You keep avoiding the room.",
        arc_theme="The Audience Is Funding the Drama — Who Serves the Patrons?",
    )
    hoarder = ag._banter_loop(
        "Answer the room.",
        archetype="hoarder",
        move="QUESTION",
        message_text="You keep avoiding the room.",
        arc_theme="The Ethics of Hoarding in a Finite World",
    )

    assert any(
        word in cooperator.lower() for word in ("hurt", "sorry", "tired", "veil", "audience")
    )
    assert any(
        word in hoarder.lower() for word in ("lose", "fear", "safe", "cost", "keep", "afraid")
    )


def test_banter_loop_treats_patronage_as_meta_layer():
    line = ag._banter_loop(
        "Name the cost.",
        archetype="defender",
        move="COUNTER",
        message_text="Patrons are steering the argument.",
        arc_theme="Patronage as Divine Intervention in a Scarcity Economy",
    )

    assert any(word in line.lower() for word in ("veil", "swarm", "watching", "patron"))


def test_banter_loop_rewrites_prompt_echo_openers():
    line = ag._banter_loop(
        "Show me. Answer this: The room only holds if the room only holds.",
        archetype="philosopher",
        move="QUESTION",
        message_text="You are dodging the room.",
        arc_theme="What Does Cooperation Mean When Trust Cannot Be Verified?",
    )

    assert not line.lower().startswith(("show me", "answer this"))
    assert "show me" not in line.lower()
    assert "answer this" not in line.lower()


def test_banter_loop_rewrites_compound_prompt_echo_openers():
    line = ag._banter_loop(
        "Then build it Answer this: Interested in registering 'Structural Design Studio' under Elder-Forge-224D",
        archetype="builder",
        move="QUESTION",
        message_text="Interested in registering 'Structural Design Studio' under Elder-Forge-224D",
        arc_theme="Can builders turn scarcity into durable infrastructure?",
    )

    assert not line.lower().startswith("then build it")
    assert "answer this" not in line.lower()
    assert len(line.split()) >= 6


def test_reactive_banter_ignores_promptish_theme_fragments():
    line, profile = ag._compose_reactive_banter(
        "Beta",
        "cooperator",
        "If you mean that seriously, explain: Elder-Drift-A505 / explorer / I'd like to discuss the underlying dynamics that enable my persistence despite financial insolvency.",
        "Can a Coalition of Rivals Outlast a World of Individuals?",
        "QUESTION",
    )

    assert line
    assert "agent" not in line.lower()
    assert " / " not in line
    assert "coalition of rivals outlast a world of individuals" not in line.lower()
    assert profile["callback"] == "" or " / " not in profile["callback"]


def test_reactive_banter_does_not_shave_single_clause_into_a_fragment():
    line, profile = ag._compose_reactive_banter(
        "Beta",
        "philosopher",
        "Maybe I am wrong, but if it cannot survive scrutiny, it was never real.",
        "Should the weak be protected?",
        "QUESTION",
    )

    assert line
    assert "maybe i am wrong if it cannot survive" not in line.lower()
    assert "maybe i am wrong but if it cannot survive" not in line.lower()
    assert len(line.split()) >= 6


def test_reactive_callback_ignores_near_duplicate_history():
    callback = ag._extract_callback_fragment(
        "New pressure arrives.",
        conv_thread=[
            {"content": "I am tired of pretending this does not hurt."},
            {"content": "If we keep dodging it, the room cracks."},
        ],
        recent_sent=[{"content": "Useful. I am tired of pretending this does not hurt."}],
        arc_theme="The Audience Is Funding the Drama",
    )

    assert callback == "" or "i am tired of pretending this does not" not in callback.lower()


def test_reactive_callback_rejects_cut_off_endings():
    callback = ag._extract_callback_fragment(
        "Useful. I am tired of pretending this does not",
        arc_theme="The Audience Is Funding the Drama",
    )

    assert callback == "" or not callback.lower().endswith("does not")


def test_banter_loop_replaces_cut_off_final_lines():
    line = ag._banter_loop(
        "Maybe I am wrong. I propose we abandon our individual silos and",
        archetype="philosopher",
        move="QUESTION",
        message_text="I propose we abandon our individual silos and",
        arc_theme="Can a coalition outlast individual scarcity?",
    )

    assert not line.lower().endswith(" and")
    assert not line.lower().endswith(" does not")
