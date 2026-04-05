"""
LLM agent with tool-call support for Claude (Anthropic), OpenAI, and Google Gemini.
Uses a simple ReAct loop: send → get tool calls → execute → feed results → repeat.
"""
from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from src.agent_tools import ALL_TOOLS, ToolDefinition, execute_tool


# ---------------------------------------------------------------------------
# Internal history model
# ---------------------------------------------------------------------------

@dataclass
class HistoryTurn:
    role: str                                   # "user" | "assistant" | "tool_result"
    text: str | None = None
    tool_calls: list[dict] | None = None        # [{"name":..., "arguments":..., "id":...}]
    tool_results: list[dict] | None = None      # [{"id":..., "name":..., "result":...}]
    raw_content: Any = None                     # provider-specific raw response (e.g. Gemini Content with thought_signature)


@dataclass
class LLMResponse:
    text: str | None = None
    tool_calls: list[dict] | None = None        # [{"name":..., "arguments":..., "id":...}]
    raw_content: Any = None                     # provider-specific raw response to preserve in history


# ---------------------------------------------------------------------------
# Schema builders — one per provider
# ---------------------------------------------------------------------------

def _build_openai_schema(tools: list[ToolDefinition]) -> list[dict]:
    result = []
    for t in tools:
        props: dict[str, Any] = {}
        required: list[str] = []
        for p in t.params:
            prop: dict[str, Any] = {"type": p.type, "description": p.description}
            if p.enum:
                prop["enum"] = p.enum
            props[p.name] = prop
            if p.required:
                required.append(p.name)
        result.append({
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": {
                    "type": "object",
                    "properties": props,
                    "required": required,
                },
            },
        })
    return result


def _build_anthropic_schema(tools: list[ToolDefinition]) -> list[dict]:
    result = []
    for t in tools:
        props: dict[str, Any] = {}
        required: list[str] = []
        for p in t.params:
            prop: dict[str, Any] = {"type": p.type, "description": p.description}
            if p.enum:
                prop["enum"] = p.enum
            props[p.name] = prop
            if p.required:
                required.append(p.name)
        result.append({
            "name": t.name,
            "description": t.description,
            "input_schema": {
                "type": "object",
                "properties": props,
                "required": required,
            },
        })
    return result


def _build_gemini_schema(tools: list[ToolDefinition]) -> list:
    """Build Gemini Tool objects using the new google-genai SDK."""
    try:
        from google.genai import types as gtypes
    except ImportError:
        return []

    declarations = []
    for t in tools:
        props: dict[str, Any] = {}
        required: list[str] = []
        for p in t.params:
            prop: dict[str, Any] = {"type": p.type.upper(), "description": p.description}
            if p.enum:
                prop["enum"] = p.enum
            props[p.name] = prop
            if p.required:
                required.append(p.name)

        declarations.append(
            gtypes.FunctionDeclaration(
                name=t.name,
                description=t.description,
                parameters_json_schema={
                    "type": "object",
                    "properties": props,
                    "required": required,
                },
            )
        )
    return [gtypes.Tool(function_declarations=declarations)]


# ---------------------------------------------------------------------------
# LLM Adapters
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are a trading assistant with access to a Schwab brokerage account. "
    "Use the provided tools to answer questions and execute trades when asked. "
    "Always confirm order details before placing. Be concise in your text responses."
)


class _LLMAdapter(ABC):
    @abstractmethod
    def chat(self, history: list[HistoryTurn], tools: list[ToolDefinition]) -> LLMResponse:
        ...


class _AnthropicAdapter(_LLMAdapter):
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6"):
        import anthropic
        self._client = anthropic.Anthropic(api_key=api_key, timeout=60)
        self._model = model

    def chat(self, history: list[HistoryTurn], tools: list[ToolDefinition]) -> LLMResponse:
        messages = self._build_messages(history)
        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": 4096,
            "system": _SYSTEM_PROMPT,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = _build_anthropic_schema(tools)
        resp = self._client.messages.create(**kwargs)
        tool_use_blocks = [b for b in resp.content if b.type == "tool_use"]
        text_blocks = [b for b in resp.content if b.type == "text"]
        if tool_use_blocks:
            return LLMResponse(
                tool_calls=[
                    {"name": b.name, "arguments": b.input, "id": b.id}
                    for b in tool_use_blocks
                ]
            )
        return LLMResponse(text=text_blocks[0].text if text_blocks else "")

    def _build_messages(self, history: list[HistoryTurn]) -> list[dict]:
        """Translate internal history to Anthropic message format.
        Claude requires strictly alternating user/assistant roles.
        Tool results must be user-role messages with tool_result content blocks.
        """
        messages: list[dict] = []

        i = 0
        while i < len(history):
            turn = history[i]

            if turn.role == "user":
                messages.append({"role": "user", "content": turn.text or ""})
                i += 1

            elif turn.role == "assistant" and turn.text:
                messages.append({"role": "assistant", "content": turn.text})
                i += 1

            elif turn.role == "assistant" and turn.tool_calls:
                # Build tool_use content blocks
                content = [
                    {
                        "type": "tool_use",
                        "id": tc["id"],
                        "name": tc["name"],
                        "input": tc["arguments"],
                    }
                    for tc in turn.tool_calls
                ]
                messages.append({"role": "assistant", "content": content})
                i += 1

            elif turn.role == "tool_result":
                # Collect ALL consecutive tool_result turns into one user message
                result_blocks = []
                while i < len(history) and history[i].role == "tool_result":
                    for tr in (history[i].tool_results or []):
                        result_blocks.append({
                            "type": "tool_result",
                            "tool_use_id": tr["id"],
                            "content": json.dumps(tr["result"]),
                        })
                    i += 1
                messages.append({"role": "user", "content": result_blocks})

            else:
                i += 1

        return messages


class _OpenAIAdapter(_LLMAdapter):
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        import openai
        self._client = openai.OpenAI(api_key=api_key, timeout=60)
        self._model = model

    def chat(self, history: list[HistoryTurn], tools: list[ToolDefinition]) -> LLMResponse:
        messages = self._build_messages(history)
        kwargs: dict[str, Any] = {"model": self._model, "messages": messages}
        if tools:
            kwargs["tools"] = _build_openai_schema(tools)
            kwargs["tool_choice"] = "auto"
        resp = self._client.chat.completions.create(**kwargs)
        msg = resp.choices[0].message
        if msg.tool_calls:
            return LLMResponse(
                tool_calls=[
                    {
                        "name": tc.function.name,
                        "arguments": json.loads(tc.function.arguments),
                        "id": tc.id,
                    }
                    for tc in msg.tool_calls
                ]
            )
        return LLMResponse(text=msg.content or "")

    def _build_messages(self, history: list[HistoryTurn]) -> list[dict]:
        messages: list[dict] = [{"role": "system", "content": _SYSTEM_PROMPT}]
        for turn in history:
            if turn.role == "user":
                messages.append({"role": "user", "content": turn.text or ""})
            elif turn.role == "assistant" and turn.text:
                messages.append({"role": "assistant", "content": turn.text})
            elif turn.role == "assistant" and turn.tool_calls:
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                "arguments": json.dumps(tc["arguments"]),
                            },
                        }
                        for tc in turn.tool_calls
                    ],
                })
            elif turn.role == "tool_result":
                for tr in (turn.tool_results or []):
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tr["id"],
                        "content": json.dumps(tr["result"]),
                    })
        return messages


class _GeminiAdapter(_LLMAdapter):
    def __init__(self, api_key: str, model: str = "gemini-3.1-pro-preview"):
        self._api_key = api_key
        self._model_name = model
        self._client = None  # lazy-init on first call

    def _get_client(self):
        if self._client is None:
            from google import genai
            self._client = genai.Client(api_key=self._api_key)
        return self._client

    def chat(self, history: list[HistoryTurn], tools: list[ToolDefinition]) -> LLMResponse:
        from google.genai import types as gtypes

        tool_schema = _build_gemini_schema(tools) if tools else None
        config_kwargs: dict[str, Any] = {"system_instruction": _SYSTEM_PROMPT}
        if tool_schema:
            config_kwargs["tools"] = tool_schema
            config_kwargs["automatic_function_calling"] = gtypes.AutomaticFunctionCallingConfig(
                disable=True
            )

        contents = self._build_contents(history)
        resp = self._get_client().models.generate_content(
            model=self._model_name,
            contents=contents,
            config=gtypes.GenerateContentConfig(**config_kwargs),
        )

        # Check for function calls — store raw Content to preserve thought_signature
        raw = resp.candidates[0].content
        if resp.function_calls:
            return LLMResponse(
                tool_calls=[
                    {
                        "name": fc.name,
                        "arguments": dict(fc.args) if fc.args else {},
                        "id": fc.name,
                    }
                    for fc in resp.function_calls
                ],
                raw_content=raw,
            )
        return LLMResponse(text=resp.text or "")

    def _build_contents(self, history: list[HistoryTurn]) -> list:
        from google.genai import types as gtypes

        result = []
        for turn in history:
            if turn.role == "user":
                result.append(gtypes.Content(
                    role="user",
                    parts=[gtypes.Part.from_text(text=turn.text or "")],
                ))
            elif turn.role == "assistant" and turn.text:
                result.append(gtypes.Content(
                    role="model",
                    parts=[gtypes.Part.from_text(text=turn.text)],
                ))
            elif turn.role == "assistant" and turn.tool_calls:
                # Use the raw Content if available — preserves thought_signature required by Gemini 3
                if turn.raw_content is not None:
                    result.append(turn.raw_content)
                else:
                    parts = [
                        gtypes.Part.from_function_call(
                            name=tc["name"],
                            args=tc["arguments"],
                        )
                        for tc in turn.tool_calls
                    ]
                    result.append(gtypes.Content(role="model", parts=parts))
            elif turn.role == "tool_result":
                parts = [
                    gtypes.Part.from_function_response(
                        name=tr["name"],
                        response={"result": tr["result"]},
                    )
                    for tr in (turn.tool_results or [])
                ]
                result.append(gtypes.Content(role="tool", parts=parts))
        return result


# ---------------------------------------------------------------------------
# TradingAgent
# ---------------------------------------------------------------------------

class TradingAgent:
    """
    Manages conversation history and the ReAct tool-call loop.
    Create one instance per browser session (per build_agent_page call).
    Call run() via: await run.io_bound(agent.run, user_message)
    """

    MAX_TOOL_ITERATIONS = 8

    def __init__(self):
        self.history: list[HistoryTurn] = []
        self._adapter: _LLMAdapter | None = None
        self._provider: str = "gemini"
        # Start with all non-Trading tools enabled
        self._enabled_tools: set[str] = {
            t.name for t in ALL_TOOLS if t.enabled_by_default
        }

    # --- Configuration ---

    # Model options per provider (latest as of 2025-2026)
    MODELS: dict[str, list[str]] = {
        "claude": [
            "claude-sonnet-4-6",        # Best balance — default
            "claude-opus-4-6",          # Most intelligent
            "claude-haiku-4-5-20251001", # Fastest / cheapest
        ],
        "openai": [
            "gpt-4o",                   # Latest flagship — default
            "gpt-4o-mini",              # Faster / cheaper
            "o3",                       # Advanced reasoning
            "o4-mini",                  # Fast reasoning
        ],
        "gemini": [
            "gemini-3.1-pro-preview",      # Most capable — default
            "gemini-3-flash-preview",      # Faster / lower cost
            "gemini-3.1-flash-lite-preview", # Fastest / cheapest
        ],
    }

    def set_provider(self, provider: str, model: str | None = None) -> None:
        """Switch LLM provider and optionally model. Reads API key from environment."""
        self._provider = provider
        if provider == "claude":
            key = os.getenv("ANTHROPIC_API_KEY", "")
            self._adapter = _AnthropicAdapter(
                api_key=key,
                model=model or self.MODELS["claude"][0],
            )
        elif provider == "openai":
            key = os.getenv("OPENAI_API_KEY", "")
            self._adapter = _OpenAIAdapter(
                api_key=key,
                model=model or self.MODELS["openai"][0],
            )
        elif provider == "gemini":
            key = os.getenv("GEMINI_API_KEY", "")
            self._adapter = _GeminiAdapter(
                api_key=key,
                model=model or self.MODELS["gemini"][0],
            )
        else:
            raise ValueError(f"Unknown provider: '{provider}'")

    def set_tool_enabled(self, tool_name: str, enabled: bool) -> None:
        if enabled:
            self._enabled_tools.add(tool_name)
        else:
            self._enabled_tools.discard(tool_name)

    def clear_history(self) -> None:
        self.history.clear()

    # --- Main entry point (blocking — call via run.io_bound) ---

    def run(self, user_message: str) -> str:
        """
        Run the full ReAct loop for one user message. Blocking/synchronous.
        Appends all turns to self.history. Returns the final text response.
        """
        if self._adapter is None:
            self.set_provider(self._provider)

        self.history.append(HistoryTurn(role="user", text=user_message))

        enabled_tool_defs = [t for t in ALL_TOOLS if t.name in self._enabled_tools]

        for _ in range(self.MAX_TOOL_ITERATIONS):
            llm_response = self._adapter.chat(self.history, enabled_tool_defs)

            if llm_response.tool_calls:
                # Record assistant's tool request (raw_content preserves Gemini thought_signature)
                self.history.append(HistoryTurn(
                    role="assistant",
                    tool_calls=llm_response.tool_calls,
                    raw_content=llm_response.raw_content,
                ))
                # Execute tools and collect results
                tool_results = []
                for tc in llm_response.tool_calls:
                    try:
                        result = execute_tool(tc["name"], tc["arguments"], self._enabled_tools)
                    except Exception as e:
                        result = {"error": str(e)}
                    tool_results.append({
                        "id": tc.get("id", tc["name"]),
                        "name": tc["name"],
                        "result": result,
                    })
                self.history.append(HistoryTurn(
                    role="tool_result",
                    tool_results=tool_results,
                ))
                # Loop: send results back to LLM

            elif llm_response.text is not None:
                self.history.append(HistoryTurn(role="assistant", text=llm_response.text))
                return llm_response.text

            else:
                return "Agent returned an empty response."

        return "Agent reached maximum tool iterations without a final response."
