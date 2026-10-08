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
    args = parser.parse_args(argv)
    from .tools import ToolService
    enabled = ToolService.DEFAULT | ({"write_file"} if args.enable_write else set())
    runtime = Runtime(repository=args.repository, state=args.state, workspace=args.workspace,
                      principal=args.principal, session=args.session, enabled=enabled,
                      native_data=args.native_data)
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
    else:
        result = getattr(runtime, args.command)()
    print(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
