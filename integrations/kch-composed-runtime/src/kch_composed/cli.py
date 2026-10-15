"""Explicit local host configuration; no model calls occur unless 'run' is used."""
import argparse
import json
from pathlib import Path
import sys
from .model import ChatCompletionsClient, strict_json_loads
from .runtime import Runtime


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--principal", required=True)
    parser.add_argument("--session", required=True)
    parser.add_argument("--native-data", type=Path)
    parser.add_argument("--enable-write", action="store_true")
    parser.add_argument("--federation-config", type=Path,
                        help="Explicit host-owned allowlist and SuperMCP binding")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("mcp", "inspect", "recover-tools", "cancel", "resume"):
        commands.add_parser(name)
    invoke = commands.add_parser("invoke")
    invoke.add_argument("--call-id", required=True)
    invoke.add_argument("--tool", required=True)
    invoke.add_argument("--arguments-file", type=Path, required=True)
    run = commands.add_parser("run")
    run.add_argument("--endpoint", required=True)
    run.add_argument("--model", required=True)
    run.add_argument("--api-key-env")
    run.add_argument("--prompt-file", type=Path)
    run.add_argument("--max-steps", type=int, default=16)
    run.add_argument("--retry-model", action="store_true")
    run.add_argument("--options-file", type=Path)
    export = commands.add_parser("checkpoint-export")
    export.add_argument("--output", type=Path, required=True)
    intake = commands.add_parser("checkpoint-import")
    intake.add_argument("--input", type=Path, required=True)
    intake.add_argument("--source-id", action="append", default=[],
                        help="Explicit source to materialize as evidence; repeatable")
    commands.add_parser("federation-discover")
    args = parser.parse_args(argv)
    from .tools import ToolService
    enabled = ToolService.DEFAULT | ({"write_file"} if args.enable_write else set())
    federation = None
    if args.federation_config:
        from .federation import FederationBridge
        config = strict_json_loads(args.federation_config.read_bytes())
        expected = {"principal": args.principal, "workspace": str(args.workspace.resolve()),
                    "session": args.session, "repository": str(args.repository.resolve())}
        if any(config.get(k) != v for k, v in expected.items()):
            parser.error("Federation identity/repository differs from the explicit CLI binding")
        federation = FederationBridge.from_config(config, audit_path=args.state / "federation.sqlite")
    runtime = Runtime(repository=args.repository, state=args.state, workspace=args.workspace,
                      principal=args.principal, session=args.session, enabled=enabled,
                      native_data=args.native_data, federation=federation)
    try:
        return execute_command(args, runtime)
    finally:
        runtime.close()


def execute_command(args, runtime):
    if args.command == "mcp":
        from .mcp import serve
        serve(runtime)
        return 0
    if args.command == "run":
        options = strict_json_loads(args.options_file.read_bytes()) if args.options_file else None
        client = ChatCompletionsClient(args.endpoint, args.model,
                                      api_key_env=args.api_key_env, request_options=options)
        result = runtime.run(client, args.prompt_file.read_text() if args.prompt_file else None,
                             max_steps=args.max_steps, retry_model=args.retry_model,
                             binding={"endpoint": args.endpoint, "model": args.model, "options": options})
    elif args.command == "invoke":
        result = runtime.execute(args.call_id, args.tool, strict_json_loads(args.arguments_file.read_bytes()))
    elif args.command == "recover-tools":
        result = runtime.recover_tools()
    elif args.command == "checkpoint-export":
        from .checkpoint import export_checkpoint
        result = export_checkpoint(runtime, args.output)
    elif args.command == "checkpoint-import":
        from .checkpoint import import_checkpoint_evidence
        result = import_checkpoint_evidence(runtime, args.input, source_ids=args.source_id)
    elif args.command == "federation-discover":
        if runtime.tools.federation is None:
            raise ValueError("federation-discover requires --federation-config")
        result = {"binding": runtime.tools.federation.binding(),
                  "catalogue": runtime.tools.federation.discover(),
                  "exposed_tools": runtime.tools.federation.schemas()}
    else:
        result = getattr(runtime, args.command)()
    print(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
