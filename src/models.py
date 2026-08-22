"""Bedrock model identifiers used by Lambda and documented in CDK context."""

from __future__ import annotations

# Reasoning tier (default). In-region id; geo profiles: us. / eu. / au. / global.
DEFAULT_REASONING_TIER_MODEL_ID = "anthropic.claude-sonnet-5"
DEFAULT_BEDROCK_MODEL_ID = DEFAULT_REASONING_TIER_MODEL_ID
SONNET_5_ID_SUBSTRING = "claude-sonnet-5"

# Fast tier — intent classification, chit-chat, simple Q&A, lightweight lookup.
DEFAULT_FAST_TIER_MODEL_ID = "anthropic.claude-3-5-haiku-20241022-v1:0"
