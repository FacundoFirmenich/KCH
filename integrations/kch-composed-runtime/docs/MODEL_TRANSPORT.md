# Model transport: scope and integration contract

Implemented on 2026-10-08. Python 3.11+ standard library only.

`ChatCompletionsClient(endpoint, model, api_key_env=None, timeout=60, *, request_options=None)` implements one non-streaming Chat Completions request per `complete(messages, tools)` invocation. It returns the complete assistant message dictionary. The caller owns durable storage, history ordering, permission checks, tool execution and the next request.

The endpoint is explicit. A base URL receives the suffix `/chat/completions`; a complete URL ending with that suffix is used as configured. There is no provider selection, credential discovery, model substitution or request during construction. HTTPS uses the platform CA store. Plain HTTP accepts only explicitly configured loopback addresses or `localhost`. HTTP redirects and environment-derived proxies are disabled. Remote endpoints require an explicitly named credential environment variable; local endpoints may be keyless. The client reads a credential immediately before transport and does not place it in client state, request bodies, returned metadata or exception strings.

## Native state and strict parsing

Preserve each returned message as a whole in its original conversation position. In particular, keep `reasoning_content`, `tool_calls`, call IDs and additional native fields. Do not replace the message with a reconstruction containing only `content`. The client returns a deep copy and does not mutate input history. Serialization preserves JSON values and order of the message sequence; it does not promise byte-identical JSON whitespace from the provider.

`parse_tool_arguments(arguments)` accepts either a JSON-encoded object string or an already decoded JSON object, returning a validated object for the tool dispatcher. The source message retains whichever representation the provider used. Duplicate keys in received JSON, non-finite numbers, float overflow, non-object arguments, missing/repeated call IDs, unsupported call types and invalid function names are rejected. JSON schema validation and the tool's permission boundary remain the dispatcher's responsibility. Function names use the documented `[A-Za-z0-9_-]{1,64}` form; expose other native names through a reversible registry mapping.

Successful completion requires one assistant choice and `finish_reason` equal to `stop` or `tool_calls`, consistent with the payload. A refusal, content filtering, truncation, legacy `function_call`, unknown finish reason, incomplete message or protocol error raises an explicit exception before a tool can execute. Provider usage is retained only when reported; absent usage remains `None`. The client never estimates tokens or cost.

The per-attempt memory properties are `last_response`, `last_usage` and `last_finish_reason`. They reset before every attempt. A received JSON envelope may remain available as `last_response` even when its completion fails validation; a caller must not treat its presence as dispatch authorization. The client does not write logs or files. Session persistence must retain native state while protecting private conversation data.

## Explicit provider options

`request_options` currently accepts `thinking`, `reasoning_effort`, `max_tokens`, `max_completion_tokens`, `temperature`, `top_p`, `presence_penalty`, `frequency_penalty`, `response_format`, `tool_choice`, `parallel_tool_calls`, `stop`, and `seed`. Values must be finite JSON data. Accepted option names are transport capabilities, not a claim that every endpoint accepts every option or value. The endpoint may reject an unsupported option. There is no retry that removes an option or silently changes its meaning.

The fields `model`, `messages`, `tools`, `stream` and `n` cannot be overridden through options. Streaming and multi-choice generation are outside this client's scope. Native Responses, Anthropic Messages and provider-specific endpoints need separate adapters; sharing a brand or model name does not establish protocol compatibility.

For Z.ai's documented preserved-thinking mode, an explicitly chosen request option is `{"thinking":{"type":"enabled","clear_thinking":false}}`. This is never injected automatically. Its effective behavior depends on the selected model and endpoint. The official API documentation distinguishes Coding Plan and standard endpoint defaults. DeepSeek's currently documented tool path requires returning the entire historical reasoning field when requests carry tools. Both requirements motivate preserving messages before any future context-folding policy is allowed to alter them.

## Failure and verification boundary

There are no automatic retries. Transport failures can leave delivery uncertain. `ModelTransportError.delivery_uncertain` is also true for 5xx, 408 and 429 responses; an HTTP failure does not prove that a remote request incurred no processing or cost. Redirects are refused rather than followed with conversation data or credentials. The maximum received body is 16 MiB. HTTP failures omit remote response bodies from exceptions because such bodies can echo sensitive input.

The local verification suite includes actual HTTP transport over loopback, preservation of the documented DeepSeek tool message, explicit Z.ai option forwarding, parser rejection cases, no credential persistence in client state, redirect refusal and one-request-only failure behavior. These are software protocol tests. They do not validate provider uptime, a real model's task performance, billing behavior or end-to-end agent integration. No paid or external model request was made for this verification.

Primary sources inspected on 2026-10-08:

- [DeepSeek Thinking Mode](https://api-docs.deepseek.com/guides/thinking_mode/): full historical reasoning replay when tools are sent; whole-message append pattern.
- [DeepSeek Chat Completions schema](https://api-docs.deepseek.com/api/create-chat-completion/): function arguments as a JSON string; validate arguments before execution. The schema was retrievable through search; direct page opening timed out during this review.
- [Z.ai Thinking Mode](https://docs.z.ai/guides/capabilities/thinking-mode): preserved thinking and intact ordering; explicit `clear_thinking` option and endpoint-specific defaults.
- [Z.ai Chat Completion](https://docs.z.ai/api-reference/llm/chat-completion): current non-streaming response schema describes function arguments as an object, while the streaming example assembles a string. The client supports both representations without claiming that this documentation difference is a verified live API result.
