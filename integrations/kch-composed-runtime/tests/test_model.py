"""Protocol tests, not model-quality results or live-provider validation.

The positive tool message below projects the documented DeepSeek example at
https://api-docs.deepseek.com/guides/thinking_mode/ (retrieved 2026-10-08).
The envelope follows its Chat Completions schema. Local HTTP serves this
documented protocol case; it is not a model, simulated benchmark or API result.
Invalid cases are deliberate protocol mutations. Z.ai preservation requirements:
https://docs.z.ai/guides/capabilities/thinking-mode .
"""

import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from kch_composed.model import (
    ChatCompletionsClient, ModelConfigurationError, ModelProtocolError,
    ModelRefusalError, ModelTransportError, ModelTruncationError,
    parse_completion_response, parse_tool_arguments, strict_json_loads, validate_message_history,
)


DOCUMENTED_MESSAGE = {
    "role": "assistant", "content": "",
    "reasoning_content": "Today is 2026-04-19, so tomorrow is 2026-04-20. Now I'll call the weather function for Hangzhou.",
    "tool_calls": [{
        "id": "call_00_H2SCW6136vWJGq9SQlBuhVt4", "type": "function",
        "function": {"name": "get_weather", "arguments": '{"location": "Hangzhou", "date": "2026-04-20"}'},
    }],
}


def documented_envelope():
    return {"choices": [{"index": 0, "finish_reason": "tool_calls",
                         "message": copy.deepcopy(DOCUMENTED_MESSAGE)}]}


class ParserTests(unittest.TestCase):
    def test_native_message_and_original_arguments_are_preserved(self):
        envelope = documented_envelope()
        # Protocol extension retention, not a claimed provider-generated field.
        envelope["choices"][0]["message"]["extension"] = {"opaque": [1, 2]}
        result = parse_completion_response(envelope)
        self.assertEqual(result, envelope["choices"][0]["message"])
        self.assertIsNot(result, envelope["choices"][0]["message"])
        self.assertEqual(parse_tool_arguments(result["tool_calls"][0]["function"]["arguments"]),
                         {"location": "Hangzhou", "date": "2026-04-20"})

    def test_rejects_non_object_or_ambiguous_tool_arguments(self):
        cases = ["[]", "null", '"text"', '{"x":NaN}', '{"x":Infinity}',
                 '{"x":-Infinity}', '{"x":1e999}', '{"x":1,"x":2}',
                 '{"x":{"y":1,"y":2}}', "{", {"x": float("nan")}, {1: "invalid key"},
                 {"x": {"y": float("inf")}}, {"x": (1, 2)}]
        for arguments in cases:
            with self.subTest(arguments=arguments), self.assertRaises(ModelProtocolError):
                parse_tool_arguments(arguments)

    def test_object_arguments_preserve_provider_representation(self):
        envelope = documented_envelope()
        call = envelope["choices"][0]["message"]["tool_calls"][0]
        call["function"]["arguments"] = {"location": "Hangzhou", "date": "2026-04-20"}
        message = parse_completion_response(envelope)
        arguments = message["tool_calls"][0]["function"]["arguments"]
        self.assertIsInstance(arguments, dict)
        self.assertEqual(parse_tool_arguments(arguments), arguments)

    def test_rejects_duplicate_or_missing_ids(self):
        for ident in (None, "", "\n"):
            envelope = documented_envelope()
            envelope["choices"][0]["message"]["tool_calls"][0]["id"] = ident
            with self.subTest(ident=ident), self.assertRaises(ModelProtocolError):
                parse_completion_response(envelope)
        envelope = documented_envelope()
        calls = envelope["choices"][0]["message"]["tool_calls"]
        calls.append(copy.deepcopy(calls[0]))
        with self.assertRaises(ModelProtocolError):
            parse_completion_response(envelope)

    def test_truncation_refusal_and_provider_error_cannot_dispatch(self):
        for finish, error in (("length", ModelTruncationError),
                              ("content_filter", ModelRefusalError),
                              ("insufficient_system_resource", ModelProtocolError),
                              (None, ModelProtocolError)):
            envelope = documented_envelope()
            envelope["choices"][0]["finish_reason"] = finish
            with self.subTest(finish=finish), self.assertRaises(error):
                parse_completion_response(envelope)
        envelope = documented_envelope()
        envelope["choices"][0]["message"]["refusal"] = "Protocol refusal case"
        with self.assertRaises(ModelRefusalError):
            parse_completion_response(envelope)
        with self.assertRaises(ModelProtocolError):
            parse_completion_response({"error": {"code": "invalid_request_error"}})

    def test_finish_reason_must_match_calls_and_no_reasoning_only_completion(self):
        envelope = documented_envelope()
        envelope["choices"][0]["finish_reason"] = "stop"
        with self.assertRaises(ModelProtocolError):
            parse_completion_response(envelope)
        envelope["choices"][0]["message"]["tool_calls"] = []
        with self.assertRaises(ModelProtocolError):
            parse_completion_response(envelope)

    def test_legacy_tools_multiple_choices_and_invalid_usage_are_rejected(self):
        envelope = documented_envelope()
        envelope["choices"][0]["message"]["function_call"] = {"name": "get_weather"}
        with self.assertRaises(ModelProtocolError):
            parse_completion_response(envelope)
        envelope = documented_envelope()
        envelope["choices"].append(copy.deepcopy(envelope["choices"][0]))
        with self.assertRaises(ModelProtocolError):
            parse_completion_response(envelope)
        for count in (-1, 1.5, True, "1"):
            envelope = documented_envelope()
            envelope["usage"] = {"total_tokens": count}
            with self.subTest(count=count), self.assertRaises(ModelProtocolError):
                parse_completion_response(envelope)

    def test_strict_wire_json_rejects_duplicates_and_invalid_utf8(self):
        for payload in (b'{"choices":[],"choices":[]}', b'{"x":"\xff"}', b'{"x":NaN}'):
            with self.subTest(payload=payload), self.assertRaises(ModelProtocolError):
                strict_json_loads(payload)

    def test_tool_pairing_rejects_missing_orphan_duplicate_and_interrupted_batches(self):
        assistant = copy.deepcopy(DOCUMENTED_MESSAGE)
        result = {"role": "tool", "tool_call_id": assistant["tool_calls"][0]["id"],
                  "content": "Documented protocol result"}
        for history in ([assistant], [result], [assistant, result, result],
                        [assistant, {"role": "user", "content": "interrupted batch"}],
                        [assistant, {**result, "tool_call_id": "different-batch"}]):
            with self.subTest(history=history), self.assertRaises(ModelProtocolError):
                validate_message_history(history)
        self.assertEqual(validate_message_history([assistant], allow_pending=True), [result["tool_call_id"]])
        self.assertEqual(validate_message_history([assistant, result]), [])
        # IDs can recur after their earlier batch was completely paired.
        self.assertEqual(validate_message_history([assistant, result, assistant, result]), [])


class ConfigurationTests(unittest.TestCase):
    def test_https_and_loopback_endpoint_rules(self):
        for endpoint in ("http://example.com/v1", "http://192.168.1.1/v1",
                         "http://localhost.evil/v1", "https://user:secret@example.com/v1",
                         "https://example.com/v1?key=secret", "https://example.com/v1#secret",
                         "file:///tmp/model", "https://example.com:invalid", " https://example.com"):
            with self.subTest(endpoint=endpoint), self.assertRaises(ModelConfigurationError):
                ChatCompletionsClient(endpoint, "explicit-model", "KCH_TEST_KEY")
        for endpoint in ("http://127.0.0.1:8000/v1", "http://[::1]:8000/v1", "http://localhost:8000/v1"):
            client = ChatCompletionsClient(endpoint, "explicit-model")
            self.assertEqual(client.endpoint, endpoint + "/chat/completions")
        client = ChatCompletionsClient("https://example.com/v1/chat/completions", "explicit-model", "KCH_TEST_KEY")
        self.assertEqual(client.endpoint, "https://example.com/v1/chat/completions")

    def test_no_remote_default_credentials_or_implicit_protocol_options(self):
        with self.assertRaises(ModelConfigurationError):
            ChatCompletionsClient("https://example.com/v1", "explicit-model")
        for options in ({"stream": True}, {"model": "other"}, {"api_key": "not-allowed"}, {"top_p": float("nan")}):
            with self.subTest(options=options), self.assertRaises(ModelConfigurationError):
                ChatCompletionsClient("http://127.0.0.1", "explicit-model", request_options=options)
        for timeout in (0, -1, True, float("inf")):
            with self.subTest(timeout=timeout), self.assertRaises(ModelConfigurationError):
                ChatCompletionsClient("http://127.0.0.1", "explicit-model", timeout=timeout)

    def test_missing_configured_key_fails_before_network(self):
        client = ChatCompletionsClient("https://example.com/v1", "explicit-model", "KCH_MODEL_PROTOCOL_TEST_MISSING_KEY")
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(ModelConfigurationError):
            client.complete([{"role": "user", "content": "Protocol request"}], [])


class HTTPTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                size = int(self.headers.get("Content-Length", "0"))
                self.server.received.append({"path": self.path,
                    "authorization": self.headers.get("Authorization"),
                    "body": json.loads(self.rfile.read(size))})
                self.send_response(self.server.status)
                self.send_header("Content-Type", "application/json")
                if self.server.status == 302:
                    self.send_header("Location", "/must-not-follow")
                self.end_headers()
                self.wfile.write(self.server.payload)

            def log_message(self, *args):
                pass  # Do not emit request bodies or credentials to test logs.

        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.endpoint = f"http://127.0.0.1:{cls.server.server_port}/v1"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self):
        self.server.received = []
        self.server.status = 200
        self.server.payload = json.dumps(documented_envelope()).encode()

    def test_actual_loopback_http_preserves_history_and_explicit_options(self):
        history = [{"role": "user", "content": "Protocol request"},
                   copy.deepcopy(DOCUMENTED_MESSAGE),
                   {"role": "tool", "tool_call_id": DOCUMENTED_MESSAGE["tool_calls"][0]["id"],
                    "content": "Cloudy 7~13°C"}]
        original = copy.deepcopy(history)
        options = {"thinking": {"type": "enabled", "clear_thinking": False}}
        client = ChatCompletionsClient(self.endpoint, "explicitly-configured-model", request_options=options)
        reply = client.complete(history, [])
        received = self.server.received[0]
        self.assertEqual(received["path"], "/v1/chat/completions")
        self.assertEqual(received["body"]["messages"], original)
        self.assertEqual(history, original)
        self.assertEqual(received["body"]["thinking"], options["thinking"])
        self.assertEqual(reply, DOCUMENTED_MESSAGE)
        self.assertIsNone(client.last_usage)
        self.assertEqual(client.last_finish_reason, "tool_calls")
        self.assertIsNone(received["authorization"])

    def test_env_key_only_used_in_header_and_not_client_state(self):
        client = ChatCompletionsClient(self.endpoint, "explicit-model", "KCH_PROTOCOL_TEST_KEY")
        # A noncredential sentinel exercises header placement; never an API key.
        with patch.dict(os.environ, {"KCH_PROTOCOL_TEST_KEY": "protocol-test-sentinel"}):
            client.complete([{"role": "user", "content": "Protocol request"}], [])
        self.assertEqual(self.server.received[0]["authorization"], "Bearer protocol-test-sentinel")
        self.assertNotIn("protocol-test-sentinel", json.dumps(self.server.received[0]["body"]))
        self.assertNotIn("protocol-test-sentinel", repr(client.__dict__))

    def test_http_failure_has_no_retry_or_sensitive_body(self):
        self.server.status = 503
        self.server.payload = b'{"error":{"message":"private-sentinel"}}'
        client = ChatCompletionsClient(self.endpoint, "explicit-model")
        with self.assertRaises(ModelTransportError) as caught:
            client.complete([{"role": "user", "content": "Protocol request"}], [])
        self.assertEqual(len(self.server.received), 1)
        self.assertEqual(caught.exception.status_code, 503)
        self.assertTrue(caught.exception.delivery_uncertain)
        self.assertNotIn("private-sentinel", str(caught.exception))

    def test_redirect_is_not_followed(self):
        self.server.status = 302
        client = ChatCompletionsClient(self.endpoint, "explicit-model")
        with self.assertRaises(ModelTransportError) as caught:
            client.complete([{"role": "user", "content": "Protocol request"}], [])
        self.assertEqual(caught.exception.status_code, 302)
        self.assertEqual(len(self.server.received), 1)

    def test_size_bound_and_malformed_reply(self):
        client = ChatCompletionsClient(self.endpoint, "explicit-model")
        client.MAX_RESPONSE_BYTES = 10
        with self.assertRaises(ModelProtocolError):
            client.complete([{"role": "user", "content": "Protocol request"}], [])
        client.MAX_RESPONSE_BYTES = 1024
        self.server.payload = b'{"choices":['
        with self.assertRaises(ModelProtocolError):
            client.complete([{"role": "user", "content": "Protocol request"}], [])
        self.assertIsNone(client.last_response)

    def test_invalid_history_is_rejected_before_any_http_request(self):
        client = ChatCompletionsClient(self.endpoint, "explicit-model")
        with self.assertRaises(ModelProtocolError):
            client.complete([copy.deepcopy(DOCUMENTED_MESSAGE)], [])
        self.assertEqual(self.server.received, [])


if __name__ == "__main__":
    unittest.main()
