/** Execute OpenClaw's original strict MCP client against a KCH subprocess.
 * Run with node --import /path/to/tsx/dist/loader.mjs and the upstream tsconfig.
 * No client/transport/process/model is replaced with a double.
 */
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";

const args = Object.fromEntries(Array.from({ length: (process.argv.length - 2) / 2 },
  (_, index) => [process.argv[2 + index * 2], process.argv[3 + index * 2]]));
for (const key of ["--repository", "--upstream", "--python", "--owner", "--output"]) {
  assert(args[key], `Required: ${key}`);
}
const repository = path.resolve(args["--repository"]);
const upstream = path.resolve(args["--upstream"]);
const output = path.resolve(args["--output"]);
const hash = (data) => createHash("sha256").update(data).digest("hex");
const { createMcpStdioClient } = await import(pathToFileURL(
  path.join(upstream, "src/agents/mcp-stdio-client.ts")));
const { McpServerSchema } = await import(pathToFileURL(
  path.join(upstream, "src/config/zod-schema.mcp-server.ts")));
const { resolveStdioMcpServerLaunchConfig } = await import(pathToFileURL(
  path.join(upstream, "src/agents/mcp-stdio.ts")));
// OpenClaw requires its Linux process owner to be compiled, without a TS loader.
// Use the upstream build-registration API and an unmodified compiled entrypoint.
const { registerSealedRuntimeProcessEntrypoint } = await import(pathToFileURL(
  path.join(upstream, "src/infra/runtime-process-url.ts")));
registerSealedRuntimeProcessEntrypoint("serviceChildGroupAnchor", pathToFileURL(path.resolve(args["--owner"])));
const root = await mkdtemp(path.join(tmpdir(), "kch-openclaw-acceptance-"));
const beforeCwd = process.cwd();
const sourceRelative = "integrations/kch-composed-runtime/README.md";
const expected = await readFile(path.join(repository, sourceRelative));
const receipt = {
  host: "openclaw", boundary: "ORIGINAL_CLIENT_COMPONENT_TO_KCH_SUBPROCESS",
  executed_at: new Date().toISOString(),
  upstream_commit: execFileSync("git", ["rev-parse", "HEAD"], { cwd: upstream, encoding: "utf8" }).trim(),
  source_sha256: hash(await readFile(path.join(upstream, "src/agents/mcp-stdio-client.ts"))),
  compiled_process_owner_sha256: hash(await readFile(args["--owner"])),
  model_inference: false, user_host_activated: false, checks: [],
};
let client;
try {
  const generated = JSON.parse(execFileSync(args["--python"], [
    path.join(repository, "integrations/kch-composed-runtime/profiles/generate.py"),
    "--repository", repository, "--state", path.join(root, "state"),
    "--workspace", repository, "--principal", "host-acceptance",
    "--session-prefix", "original-client", "--host", "openclaw",
    "--output", path.join(root, "profiles"),
  ], { encoding: "utf8" }));
  assert.equal(generated.host_activated, false);
  const profile = JSON.parse(await readFile(generated.generated[0], "utf8"));
  const config = McpServerSchema.parse(profile.mcp.servers.kch_composed);
  const launch = resolveStdioMcpServerLaunchConfig(config);
  assert.equal(launch.ok, true);
  receipt.checks.push("original_config_schema_and_launch_resolver");
  // This original strict client uses the current process working directory.
  // Apply the generated cwd before launch; the original transport remains intact.
  process.chdir(launch.config.cwd);
  function makeClient() {
    return createMcpStdioClient({
      command: launch.config.command, args: launch.config.args, env: {},
      clientInfo: { name: "kch-acceptance", version: "1" },
      protocolVersion: "2025-11-25", startupTimeoutMs: 15000,
      maxPendingRequests: 8, maxFrameBytes: 1048576,
      errors: {
        unavailable: (message, cause) => new Error(`unavailable: ${message}`, { cause }),
        protocol: (message, cause) => new Error(`protocol: ${message}`, { cause }),
      },
    });
  }
  async function call(name, arguments_) {
    const response = await client.request("tools/call", { name, arguments: arguments_ }, { timeoutMs: 15000 });
    return [response, JSON.parse(response.content[0].text)];
  }
  client = makeClient();
  const catalog = await client.request("tools/list", {}, { timeoutMs: 15000 });
  const names = catalog.tools.map((tool) => tool.name).sort();
  assert(names.includes("read_file") && !names.includes("write_file"));
  receipt.catalog = names;
  receipt.checks.push("original_client_discovery");
  let [response, result] = await call("read_file", { path: sourceRelative, max_bytes: 65536 });
  assert.equal(result.ok, true);
  assert.deepEqual(Buffer.from(result.value.content.data, "base64"), expected.subarray(0, 65536));
  receipt.read_sha256 = result.value.range_sha256;
  receipt.checks.push("real_repository_bytes_equal");
  [response, result] = await call("read_file", { path: "/etc/passwd" });
  assert.equal(response.isError, true);
  assert.equal(result.ok, false);
  receipt.checks.push("out_of_workspace_read_denied");
  [response, result] = await call("write_file", { path: "acceptance-must-not-exist.txt", content: "not authorized" });
  assert.equal(response.isError, true);
  assert.equal(result.ok, false);
  await assert.rejects(readFile(path.join(repository, "acceptance-must-not-exist.txt")), { code: "ENOENT" });
  receipt.checks.push("disabled_write_denied_without_effect");
  [response, result] = await call("memory_ingest", { path: sourceRelative, source_id: "acceptance/readme" });
  assert.equal(result.ok, true);
  receipt.checks.push("real_file_memory_ingest");
  await client.stop();
  assert.equal(client.isAvailable(), false);
  receipt.first_cleanup = client.cleanupResult;
  receipt.checks.push("first_client_closed");
  client = makeClient();
  [response, result] = await call("memory_recall", { source_id: "acceptance/readme" });
  assert.equal(result.ok, true);
  assert.deepEqual(Buffer.from(result.value.content.data, "base64"), expected);
  receipt.checks.push("new_client_process_same_session_exact_memory");
  await client.stop();
  assert.equal(client.isAvailable(), false);
  receipt.second_cleanup = client.cleanupResult;
  receipt.checks.push("restarted_client_closed");
  const status = JSON.parse(execFileSync(launch.config.command,
    [...launch.config.args.slice(0, -1), "inspect"], { encoding: "utf8", cwd: launch.config.cwd }));
  assert.equal(status.journal, true);
  assert.equal(status.calls.length, 5);
  receipt.journal = status.journal;
  receipt.bound_session = status.scope.session;
  receipt.durable_calls = status.calls.length;
  receipt.status = "PASS";
  await writeFile(output, JSON.stringify(receipt, null, 2) + "\n");
  console.log(JSON.stringify(receipt, null, 2));
} catch (error) {
  receipt.status = "FAIL";
  receipt.error = String(error);
  receipt.causes = [];
  for (let cause = error.cause; cause; cause = cause.cause) receipt.causes.push(String(cause));
  await writeFile(output, JSON.stringify(receipt, null, 2) + "\n");
  process.exitCode = 1;
  console.error(JSON.stringify(receipt, null, 2));
} finally {
  try { await client?.stop(); } catch (error) {
    receipt.cleanup_error = String(error);
    receipt.status = "FAIL";
    await writeFile(output, JSON.stringify(receipt, null, 2) + "\n");
    process.exitCode = 1;
  }
  process.chdir(beforeCwd);
  await rm(root, { recursive: true, force: true });
}
