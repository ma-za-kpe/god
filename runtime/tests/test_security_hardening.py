from agent_env import _safe_scratch_key
from security import deny_creator_action, insecure_local_endpoints_allowed, verify_creator_token


def test_creator_token_required_by_default(monkeypatch):
    monkeypatch.delenv("LOCAL_DEV_MODE", raising=False)
    monkeypatch.delenv("ALLOW_TOKENLESS_CREATOR", raising=False)
    monkeypatch.delenv("CREATOR_GENESIS_TOKEN", raising=False)

    assert verify_creator_token(None) is False
    denied = deny_creator_action(None)
    assert denied is not None
    assert denied.status_code == 403


def test_creator_token_allows_exact_match(monkeypatch):
    monkeypatch.setenv("CREATOR_GENESIS_TOKEN", "secret-token")

    assert verify_creator_token("secret-token") is True
    assert verify_creator_token("wrong-token") is False


def test_tokenless_creator_requires_explicit_local_opt_in(monkeypatch):
    monkeypatch.setenv("LOCAL_DEV_MODE", "true")
    monkeypatch.setenv("ALLOW_TOKENLESS_CREATOR", "true")
    monkeypatch.delenv("CREATOR_GENESIS_TOKEN", raising=False)

    assert verify_creator_token(None) is True


def test_insecure_local_endpoints_are_not_enabled_by_default(monkeypatch):
    monkeypatch.delenv("LOCAL_DEV_MODE", raising=False)
    monkeypatch.delenv("ALLOW_INSECURE_LOCAL_ENDPOINTS", raising=False)

    assert insecure_local_endpoints_allowed() is False


def test_scratch_key_sanitization_removes_path_traversal():
    key = _safe_scratch_key("../../outside\\evil")

    assert "/" not in key
    assert "\\" not in key
    assert ".." not in key
    assert key == "outside_evil"
