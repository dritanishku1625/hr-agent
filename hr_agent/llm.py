from __future__ import annotations

import json
import os
from dataclasses import dataclass

try:
    from openai import OpenAI
    from openai import BadRequestError as OpenAIBadRequestError
except ImportError:
    OpenAI = None
    OpenAIBadRequestError = Exception

try:
    import anthropic
except ImportError:
    anthropic = None

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-5"


@dataclass
class ToolCallView:
    id: str
    name: str
    arguments: dict


@dataclass
class ModelReply:
    content: str
    tool_calls: list[ToolCallView]
    assistant_message: dict
    provider: str


@dataclass
class LLMClient:
    provider: str
    model: str
    raw: object

    def complete(self, system: str, messages: list, tools: list, tool_choice: str) -> ModelReply:
        last_error = None
        for _ in range(3):
            try:
                if self.provider == "anthropic":
                    return _complete_anthropic(self.raw, self.model, system, messages, tools, tool_choice)
                return _complete_openai(self.raw, self.model, system, messages, tools, tool_choice)
            except OpenAIBadRequestError as error:
                last_error = error
                if not _is_retryable_tool_error(error):
                    raise
        raise last_error


def resolve_provider() -> str:
    forced = os.environ.get("LLM_PROVIDER", "").strip().lower()
    if forced in {"groq", "anthropic"}:
        return forced
    if os.environ.get("GROQ_API_KEY"):
        return "groq"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    raise SystemExit(
        "Set GROQ_API_KEY or ANTHROPIC_API_KEY in .env. "
        "Free Groq key: https://console.groq.com/keys"
    )


def model_name(provider: str | None = None) -> str:
    active = provider or resolve_provider()
    if active == "anthropic":
        return os.environ.get("ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL)
    return os.environ.get("GROQ_MODEL", DEFAULT_GROQ_MODEL)


def build_client() -> LLMClient:
    provider = resolve_provider()
    if provider == "anthropic":
        return _build_anthropic_client()
    return _build_groq_client()


def openai_tools(tools: list[dict]) -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["input_schema"],
            },
        }
        for tool in tools
    ]


def append_tool_errors(messages: list, reply: ModelReply, error: str) -> None:
    messages.append(reply.assistant_message)
    if reply.provider == "anthropic":
        messages.append({
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": call.id,
                    "is_error": True,
                    "content": error,
                }
                for call in reply.tool_calls
            ],
        })
        return
    messages.extend(
        {
            "role": "tool",
            "tool_call_id": call.id,
            "content": error,
        }
        for call in reply.tool_calls
    )


def _build_groq_client() -> LLMClient:
    if OpenAI is None:
        raise SystemExit("Install dependencies with: pip install -r requirements.txt")
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise SystemExit("Set GROQ_API_KEY in .env, or set LLM_PROVIDER=anthropic with ANTHROPIC_API_KEY.")
    return LLMClient(
        provider="groq",
        model=model_name("groq"),
        raw=OpenAI(api_key=api_key, base_url=GROQ_BASE_URL),
    )


def _build_anthropic_client() -> LLMClient:
    if anthropic is None:
        raise SystemExit("Install dependencies with: pip install -r requirements.txt")
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit("Set ANTHROPIC_API_KEY in .env, or set LLM_PROVIDER=groq with GROQ_API_KEY.")
    return LLMClient(
        provider="anthropic",
        model=model_name("anthropic"),
        raw=anthropic.Anthropic(api_key=api_key),
    )


def _complete_openai(client, model: str, system: str, messages: list, tools: list, tool_choice: str) -> ModelReply:
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        max_tokens=800,
        messages=[{"role": "system", "content": system}, *messages],
        tools=openai_tools(tools),
        tool_choice=tool_choice,
    )
    message = response.choices[0].message
    calls = [
        ToolCallView(
            id=call.id,
            name=call.function.name,
            arguments=_parse_arguments(call.function.arguments),
        )
        for call in (message.tool_calls or [])
    ]
    assistant_message = {"role": "assistant", "content": message.content or ""}
    if message.tool_calls:
        assistant_message["tool_calls"] = [
            {
                "id": call.id,
                "type": "function",
                "function": {
                    "name": call.function.name,
                    "arguments": call.function.arguments or "{}",
                },
            }
            for call in message.tool_calls
        ]
    return ModelReply(
        content=(message.content or "").strip()[:400],
        tool_calls=calls,
        assistant_message=assistant_message,
        provider="groq",
    )


def _complete_anthropic(client, model: str, system: str, messages: list, tools: list, tool_choice: str) -> ModelReply:
    choice = {"type": "any"}
    if tool_choice == "required" and len(tools) == 1:
        choice = {"type": "tool", "name": tools[0]["name"]}
    response = client.messages.create(
        model=model,
        max_tokens=800,
        temperature=0,
        system=system,
        tools=tools,
        tool_choice=choice,
        messages=messages,
    )
    calls = [
        ToolCallView(
            id=block.id,
            name=block.name,
            arguments=block.input if isinstance(block.input, dict) else {},
        )
        for block in response.content
        if getattr(block, "type", None) == "tool_use"
    ]
    text_parts = [
        block.text
        for block in response.content
        if getattr(block, "type", None) == "text"
    ]
    return ModelReply(
        content="\n".join(text_parts).strip()[:400],
        tool_calls=calls,
        assistant_message={"role": "assistant", "content": response.content},
        provider="anthropic",
    )


def _is_retryable_tool_error(error: Exception) -> bool:
    text = str(error).lower()
    return "tool_use_failed" in text or "failed to parse tool call arguments" in text


def _parse_arguments(raw: object) -> dict:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if isinstance(parsed, dict):
        return parsed
    return {}
