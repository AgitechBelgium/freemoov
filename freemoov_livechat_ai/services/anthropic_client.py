import json
import logging
import time

import requests

_logger = logging.getLogger(__name__)

API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"

# Rough Haiku 4.5 pricing (public list, in $/M tokens). Converted to € at 0.92.
PRICE_IN_PER_MTOK_EUR = 0.92 * 1.00
PRICE_OUT_PER_MTOK_EUR = 0.92 * 5.00


class AnthropicClient:
    """Thin HTTP client for Anthropic Messages API — no external SDK needed."""

    def __init__(self, api_key, model, max_tokens=400, timeout=20):
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.timeout = timeout

    def create_message(self, system_prompt, messages):
        if not self.api_key:
            raise ValueError("Anthropic API key is not configured")
        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": system_prompt,
            "messages": messages,
        }
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }
        t0 = time.monotonic()
        resp = requests.post(API_URL, headers=headers, data=json.dumps(payload), timeout=self.timeout)
        latency_ms = int((time.monotonic() - t0) * 1000)
        if resp.status_code != 200:
            raise RuntimeError(f"Anthropic API {resp.status_code}: {resp.text[:500]}")
        data = resp.json()
        text = "".join(block.get("text", "") for block in data.get("content", []) if block.get("type") == "text")
        usage = data.get("usage", {})
        return {
            "text": text.strip(),
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "latency_ms": latency_ms,
        }


def estimate_cost_eur(input_tokens, output_tokens):
    return (input_tokens / 1_000_000) * PRICE_IN_PER_MTOK_EUR + (
        output_tokens / 1_000_000
    ) * PRICE_OUT_PER_MTOK_EUR
