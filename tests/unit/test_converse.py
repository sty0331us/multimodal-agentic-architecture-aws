"""Claude Sonnet 5 Converse payload construction."""

from __future__ import annotations

from agent.converse import BedrockConverseClient, is_claude_sonnet_5
from models import DEFAULT_BEDROCK_MODEL_ID, DEFAULT_FAST_TIER_MODEL_ID, HAIKU_4_5_ID_SUBSTRING
from settings import Settings, get_settings


def test_default_model_id_is_sonnet_5() -> None:
    get_settings.cache_clear()
    assert DEFAULT_BEDROCK_MODEL_ID == "anthropic.claude-sonnet-5"
    assert is_claude_sonnet_5("us.anthropic.claude-sonnet-5")
    assert not is_claude_sonnet_5("anthropic.claude-sonnet-4-5-20250929-v1:0")


def test_sonnet_5_omits_temperature_and_sets_adaptive_thinking() -> None:
    settings = Settings(bedrock_model_id="anthropic.claude-sonnet-5", thinking_effort="low")
    client = BedrockConverseClient(settings, client=object())
    payload = client.build_request(
        messages=[{"role": "user", "content": [{"text": "hi"}]}],
        system=[{"text": "sys"}],
        tool_config={"tools": [], "toolChoice": {"auto": {}}},
    )
    assert payload["modelId"] == "anthropic.claude-sonnet-5"
    assert payload["inferenceConfig"] == {"maxTokens": 8192}
    assert "temperature" not in payload["inferenceConfig"]
    assert payload["additionalModelRequestFields"]["thinking"] == {"type": "adaptive"}
    assert payload["additionalModelRequestFields"]["output_config"] == {"effort": "low"}
    assert payload["toolConfig"]["toolChoice"] == {"auto": {}}


def test_haiku_fast_tier_uses_temperature_and_skips_thinking() -> None:
    settings = Settings(fast_tier_max_tokens=512)
    client = BedrockConverseClient(settings, client=object())
    payload = client.build_request(
        messages=[{"role": "user", "content": [{"text": "hi"}]}],
        system=[{"text": "sys"}],
        model_id=DEFAULT_FAST_TIER_MODEL_ID,
    )
    assert payload["modelId"] == DEFAULT_FAST_TIER_MODEL_ID
    assert HAIKU_4_5_ID_SUBSTRING in payload["modelId"]
    assert payload["inferenceConfig"]["temperature"] == 0.2
    assert payload["inferenceConfig"]["maxTokens"] == 512
    assert "additionalModelRequestFields" not in payload


def test_thinking_disabled_allows_temperature() -> None:
    settings = Settings(
        bedrock_model_id="us.anthropic.claude-sonnet-5",
        thinking_type="disabled",
        temperature=0.4,
        max_tokens=1024,
    )
    client = BedrockConverseClient(settings, client=object())
    payload = client.build_request(
        messages=[{"role": "user", "content": [{"text": "hi"}]}],
        system=[{"text": "sys"}],
    )
    assert payload["inferenceConfig"]["temperature"] == 0.4
    assert payload["additionalModelRequestFields"] == {"thinking": {"type": "disabled"}}
