"""Strict, non-streaming Chat Completions transport using Python's stdlib.

This is a protocol client, not a claim of compatibility with every provider.
The caller selects the endpoint/model and explicit request options. Native
assistant fields (including reasoning_content) are returned without rewriting.
There are no implicit retries, provider switches, credential files or API calls
at import/initialization time. HTTPS uses system CA verification; unencrypted
HTTP is limited to explicitly configured loopback endpoints.
"""

from __future__ import annotations

import copy
import http.client
import ipaddress
import json
import math
import os
import re
import ssl
from typing import Any
import urllib.error
import urllib.parse
import urllib.request


class ModelError(RuntimeError):
    """Base class for explicit model-boundary failures."""


class ModelConfigurationError(ModelError):
    pass


class ModelProtocolError(ModelError):
    pass


class ModelTransportError(ModelError):
    """A transport failure must not be interpreted as permission to retry."""

    def __init__(self, message: str, *, status_code: int | None = None,
                 delivery_uncertain: bool = True):
        super().__init__(message)
        self.status_code = status_code
        self.delivery_uncertain = delivery_uncertain


class ModelRefusalError(ModelError):
    pass


class ModelTruncationError(ModelError):
    pass


def _reject_constant(value: str) -> Any:
    raise ModelProtocolError("Non-finite JSON number is not permitted")


def _finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ModelProtocolError("Non-finite JSON number is not permitted")
    return number


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ModelProtocolError("Duplicate JSON object key is not permitted")
        result[key] = value
    return result


def strict_json_loads(value: str | bytes) -> Any:
    """Reject duplicate keys, NaN/Infinity, overflow and non-UTF-8 bytes."""
    try:
        if isinstance(value, bytes):
            value = value.decode("utf-8", errors="strict")
        return json.loads(value, parse_constant=_reject_constant,
                          parse_float=_finite_float, object_pairs_hook=_unique_object)
    except (ValueError, UnicodeError, RecursionError):
        raise ModelProtocolError("Invalid JSON payload") from None


def _validate_json_tree(value: Any) -> None:
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) is float and math.isfinite(value):
        return
    if isinstance(value, list):
        for item in value:
            _validate_json_tree(item)
        return
    if isinstance(value, dict) and all(isinstance(key, str) for key in value):
        for item in value.values():
            _validate_json_tree(item)
        return
    raise ModelProtocolError("Tool arguments must contain only finite JSON values")


def parse_tool_arguments(arguments: str | dict[str, Any]) -> dict[str, Any]:
    """Parse arguments without normalizing the original wire representation."""
    if isinstance(arguments, dict):
        # Z.ai's current non-streaming response schema describes an object,
        # while DeepSeek and streamed assembled responses use a JSON string.
        try:
            _validate_json_tree(arguments)
        except RecursionError:
            raise ModelProtocolError("Tool arguments are excessively nested or cyclic") from None
        value = copy.deepcopy(arguments)
    elif isinstance(arguments, str):
        value = strict_json_loads(arguments)
    else:
        raise ModelProtocolError("Tool arguments must be a JSON object or JSON-encoded object string")
    if not isinstance(value, dict):
        raise ModelProtocolError("Tool arguments must decode to a JSON object")
    return value


_FUNCTION_NAME = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
_ENV_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
_RESERVED_OPTIONS = {"model", "messages", "tools", "stream", "n"}
_SUPPORTED_OPTIONS = {
    "thinking", "reasoning_effort", "max_tokens", "max_completion_tokens",
    "temperature", "top_p", "presence_penalty", "frequency_penalty",
    "response_format", "tool_choice", "parallel_tool_calls", "stop", "seed",
}


def _validate_tool_calls(calls: Any) -> None:
    if calls is None:
        return
    if not isinstance(calls, list):
        raise ModelProtocolError("tool_calls must be a list or null")
    ids: set[str] = set()
    for call in calls:
        if not isinstance(call, dict) or call.get("type") != "function":
            raise ModelProtocolError("Only function tool calls are supported")
        ident = call.get("id")
        if not isinstance(ident, str) or not ident.strip() or any(
                ord(c) < 32 for c in ident) or ident in ids:
            raise ModelProtocolError("Tool call IDs must be nonempty and unique")
        ids.add(ident)
        function = call.get("function")
        if not isinstance(function, dict) or not isinstance(function.get("name"), str) \
                or not _FUNCTION_NAME.fullmatch(function["name"]):
            raise ModelProtocolError("Invalid function tool name")
        parse_tool_arguments(function.get("arguments"))


def parse_completion_response(response: dict[str, Any]) -> dict[str, Any]:
    """Validate one completed choice and return its unmodified assistant data.

    A truncated/refused/inconsistent result cannot reach the tool executor.
    Unknown provider-specific message fields are preserved. No token counts or
    identifiers are manufactured when the provider omits them.
    """
    if not isinstance(response, dict):
        raise ModelProtocolError("Completion response must be a JSON object")
    if response.get("error") is not None:
        raise ModelProtocolError("Provider returned an explicit error object")
    choices = response.get("choices")
    if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
        raise ModelProtocolError("Exactly one non-streaming choice is required")
    choice = choices[0]
    message = choice.get("message")
    if not isinstance(message, dict) or message.get("role") != "assistant":
        raise ModelProtocolError("Completion is missing an assistant message")
    if message.get("refusal") not in (None, ""):
        raise ModelRefusalError("Provider returned a refusal; no tools may execute")
    finish = choice.get("finish_reason")
    if finish == "length":
        raise ModelTruncationError("Provider truncated the completion; no tools may execute")
    if finish == "content_filter":
        raise ModelRefusalError("Provider filtered the completion; no tools may execute")
    if finish not in ("stop", "tool_calls"):
        raise ModelProtocolError("Unsupported or missing completion finish_reason")
    content = message.get("content")
    if content is not None and not isinstance(content, (str, list)):
        raise ModelProtocolError("Assistant content must be text, content parts or null")
    if isinstance(content, list) and any(not isinstance(part, dict) for part in content):
        raise ModelProtocolError("Assistant content parts must be objects")
    reasoning = message.get("reasoning_content")
    if reasoning is not None and not isinstance(reasoning, str):
        raise ModelProtocolError("reasoning_content must be a string or null")
    if message.get("function_call") is not None:
        raise ModelProtocolError("Legacy function_call is unsupported; use tool_calls")
    calls = message.get("tool_calls")
    _validate_tool_calls(calls)
    if bool(calls) != (finish == "tool_calls"):
        raise ModelProtocolError("finish_reason and tool_calls disagree")
    if not calls and not content:
        raise ModelProtocolError("Completion contains neither final content nor tool calls")
    usage = response.get("usage")
    if usage is not None:
        if not isinstance(usage, dict):
            raise ModelProtocolError("usage must be an object or null")
        for name in ("prompt_tokens", "completion_tokens", "total_tokens"):
            if name in usage and (type(usage[name]) is not int or usage[name] < 0):
                raise ModelProtocolError("Provider token counts must be nonnegative integers")
    return copy.deepcopy(message)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward authorization or user context to a redirected endpoint.
        return None


class ChatCompletionsClient:
    """Explicit endpoint/model client. ``complete`` returns the whole message.

    ``endpoint`` may be a base URL (``/chat/completions`` is appended) or the
    complete endpoint. ``api_key_env`` names an environment variable, never a
    credential value. No key is required for an explicit loopback server.
    ``request_options`` is explicit opt-in; no capability is inferred by brand.
    ``last_response``/``last_usage`` stay in memory and are cleared per attempt.
    This client implements neither streaming nor Responses/Anthropic protocols.
    """

    MAX_RESPONSE_BYTES = 16 * 1024 * 1024

    def __init__(self, endpoint: str, model: str, api_key_env: str | None = None,
                 timeout: float = 60, *, request_options: dict[str, Any] | None = None):
        if not isinstance(endpoint, str) or not endpoint or any(c.isspace() for c in endpoint):
            raise ModelConfigurationError("An explicit endpoint URL is required")
        try:
            parsed = urllib.parse.urlsplit(endpoint)
            host = parsed.hostname
            parsed.port  # Validate port before any network operation.
        except ValueError:
            raise ModelConfigurationError("Invalid endpoint URL") from None
        if parsed.scheme not in ("http", "https") or not host or parsed.username is not None \
                or parsed.password is not None or parsed.query or parsed.fragment:
            raise ModelConfigurationError("Endpoint must use HTTP(S), without URL credentials/query/fragment")
        try:
            loopback = ipaddress.ip_address(host).is_loopback
        except ValueError:
            loopback = host.lower() == "localhost"
        if parsed.scheme != "https" and not loopback:
            raise ModelConfigurationError("Unencrypted HTTP is allowed only for explicit loopback endpoints")
        if not isinstance(model, str) or not model.strip():
            raise ModelConfigurationError("An explicit model identifier is required")
        if api_key_env is not None and (not isinstance(api_key_env, str) or not _ENV_NAME.fullmatch(api_key_env)):
            raise ModelConfigurationError("api_key_env must be an environment variable name")
        if not loopback and not api_key_env:
            raise ModelConfigurationError("Remote endpoints require an explicit credential environment variable")
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) \
                or not math.isfinite(timeout) or timeout <= 0:
            raise ModelConfigurationError("timeout must be a positive finite number")
        options = request_options if request_options is not None else {}
        if not isinstance(options, dict) or any(key in _RESERVED_OPTIONS for key in options) \
                or any(key not in _SUPPORTED_OPTIONS for key in options):
            raise ModelConfigurationError("Unsupported or reserved request option")
        try:
            json.dumps(options, allow_nan=False)
        except (ValueError, TypeError, RecursionError):
            raise ModelConfigurationError("Request options must be finite JSON data") from None
        path = parsed.path.rstrip("/")
        if not path.endswith("/chat/completions"):
            path += "/chat/completions"
        self.endpoint = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))
        self.model = model
        self.api_key_env = api_key_env
        self.timeout = timeout
        self.request_options = copy.deepcopy(options)
        self.last_response: dict[str, Any] | None = None
        self.last_usage: dict[str, Any] | None = None
        self.last_finish_reason: str | None = None

    def complete(self, messages: list[dict[str, Any]],
                 tools: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        self.last_response = self.last_usage = self.last_finish_reason = None
        if not isinstance(messages, list) or not messages or any(
                not isinstance(message, dict) or message.get("role") not in
                ("system", "developer", "user", "assistant", "tool") for message in messages):
            raise ModelProtocolError("messages must contain role-bearing JSON objects")
        for message in messages:
            if message["role"] == "assistant":
                _validate_tool_calls(message.get("tool_calls"))
        if tools is not None:
            if not isinstance(tools, list):
                raise ModelProtocolError("tools must be a list or None")
            names: set[str] = set()
            for tool in tools:
                function = tool.get("function") if isinstance(tool, dict) else None
                name = function.get("name") if isinstance(function, dict) else None
                if not isinstance(tool, dict) or tool.get("type") != "function" \
                        or not isinstance(name, str) or not _FUNCTION_NAME.fullmatch(name) or name in names:
                    raise ModelProtocolError("Tools require distinct, valid function names")
                names.add(name)
        payload = {**self.request_options, "model": self.model, "messages": messages, "stream": False}
        if tools is not None:
            payload["tools"] = tools
        try:
            body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
        except (ValueError, TypeError, UnicodeError, RecursionError):
            raise ModelProtocolError("Request must be finite, UTF-8 JSON data") from None
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.api_key_env:
            key = os.environ.get(self.api_key_env)
            if not key or not key.strip() or any(ord(c) < 32 or ord(c) > 126 for c in key):
                raise ModelConfigurationError("Credential environment variable is missing, empty or invalid")
            headers["Authorization"] = "Bearer " + key
        request = urllib.request.Request(self.endpoint, data=body, headers=headers, method="POST")
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), _NoRedirect(),
            urllib.request.HTTPSHandler(context=ssl.create_default_context()))
        try:
            with opener.open(request, timeout=self.timeout) as response:
                if response.status != 200:
                    raise ModelTransportError("Provider returned an unexpected HTTP status",
                                              status_code=response.status, delivery_uncertain=False)
                data = response.read(self.MAX_RESPONSE_BYTES + 1)
        except urllib.error.HTTPError as exc:
            code = exc.code
            exc.close()
            # Do not include provider error bodies, URLs, credentials or prompts.
            raise ModelTransportError(f"Provider returned HTTP {code}; request was not retried",
                                      status_code=code,
                                      delivery_uncertain=code >= 500 or code in (408, 429)) from None
        except (urllib.error.URLError, OSError, TimeoutError, http.client.HTTPException):
            raise ModelTransportError("Model transport failed; delivery may be uncertain; request was not retried") from None
        if len(data) > self.MAX_RESPONSE_BYTES:
            raise ModelProtocolError("Provider response exceeds the configured transport bound")
        decoded = strict_json_loads(data)
        if isinstance(decoded, dict):
            self.last_response = decoded
            choices = decoded.get("choices")
            if isinstance(choices, list) and len(choices) == 1 and isinstance(choices[0], dict):
                self.last_finish_reason = choices[0].get("finish_reason")
        message = parse_completion_response(decoded)
        self.last_usage = copy.deepcopy(decoded.get("usage"))
        return message
