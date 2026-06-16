"""Content bank pre-generation tests."""

from content_bank import ContentBankSurface, build_content_bank_state, build_content_bank_status


def _snapshot() -> dict:
    return {
        "epoch": 654,
        "world_id": "local-dev-world-1",
        "stats": {
            "living_count": 5,
            "events_total": 22,
            "service_purchases_24h": 4,
        },
        "audience": {
            "patronage_index": 18.0,
            "raid_waves_24h": 1,
            "chat_pressure": 9,
        },
        "showrunner": {
            "scene": "market-watch",
            "speaker": "Alpha",
            "headline": "Alpha: The market is moving.",
        },
        "agents": [
            {"soul_id": "s-alpha", "current_name": "Alpha", "is_alive": True, "balance_usdc": 9.0, "generation": 2},
            {"soul_id": "s-beta", "current_name": "Beta", "is_alive": True, "balance_usdc": 6.0, "generation": 1},
            {"soul_id": "s-gamma", "current_name": "Gamma", "is_alive": True, "balance_usdc": 4.5, "generation": 1},
        ],
        "events": [],
        "messages": [],
    }


def test_content_bank_builds_future_story_assets():
    state = ContentBankSurface().compose(_snapshot())

    assert state.enabled is True
    assert state.bank_id
    assert state.arc_count >= 3
    assert state.dialogue_count == state.arc_count
    assert state.scene_count == state.arc_count
    assert state.clip_count <= state.arc_count
    assert "future arc" in state.summary.lower()
    assert state.cards[0]["label"] == "Horizon"


def test_content_bank_state_serializes():
    payload = build_content_bank_state(_snapshot())

    assert payload["focus"] in ("patron-funded escalation", "raid aftermath", "market pressure", "slow burn")
    assert payload["assets"]
    assert payload["commands"][0]["action"] == "cache_story_bank"


def test_content_bank_status_exposes_asset_types():
    status = build_content_bank_status()

    assert status["enabled"] is True
    assert "arc" in status["supported_asset_types"]
