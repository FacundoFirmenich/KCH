import { spawn, spawnSync } from 'node:child_process';
import { randomUUID } from 'node:crypto';
import { realpathSync } from 'node:fs';
import { dirname, isAbsolute, resolve, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

export const name = 'kch-deepseek-native';
export const inject = ['tools', 'agents'];
const directory = dirname(fileURLToPath(import.meta.url));
const bridge = resolve(directory, 'native_bridge.py');
const mappedNames = Object.freeze({ read: 'read_file', read_image: 'view_image', write: 'write', edit: 'edit', bash: 'exec_command' });

function within(root, path) {
  const rel = relative(root, path);
  return rel === '' || (!rel.startsWith(`..${sep}`) && rel !== '..' && !isAbsolute(rel));
}

function validateConfig(input) {
  if (!input || typeof input !== 'object') throw new Error('KCH_CONFIG_REQUIRED');
  const config = { python: 'python3', timeoutMs: 15000, maxOutputBytes: 1048576, ...input };
  for (const key of ['nativeRoot', 'dataDir', 'workspaceRoot']) {
    if (typeof config[key] !== 'string' || !isAbsolute(config[key])) throw new Error(`KCH_ABSOLUTE_PATH_REQUIRED:${key}`);
    config[key] = realpathSync(config[key]);
  }
  if (typeof config.namespace !== 'string' || !/^[A-Za-z0-9._-]+$/.test(config.namespace)) throw new Error('KCH_NAMESPACE_REQUIRED');
  for (const key of ['timeoutMs', 'maxOutputBytes']) {
    if (!Number.isSafeInteger(config[key]) || config[key] < 1) throw new Error(`KCH_INVALID_LIMIT:${key}`);
  }
  if (typeof config.python !== 'string' || !config.python) throw new Error('KCH_PYTHON_REQUIRED');
  return Object.freeze(config);
}

function request(config, action, payload) {
  return JSON.stringify({ nativeRoot: config.nativeRoot, dataDir: config.dataDir, action, payload });
}

function invokeSync(config, action, payload) {
  const result = spawnSync(config.python, [bridge], {
    input: request(config, action, payload), encoding: 'utf8', timeout: config.timeoutMs,
    maxBuffer: config.maxOutputBytes, windowsHide: true,
  });
  if (result.error || result.status !== 0) throw new Error(`KCH_BRIDGE_FAILURE:${result.error?.message ?? result.stderr.trim()}`);
  return JSON.parse(result.stdout);
}

function invoke(config, action, payload, signal) {
  return new Promise((accept, reject) => {
    if (signal?.aborted) { reject(new Error('KCH_CANCELLED')); return; }
    const child = spawn(config.python, [bridge], { stdio: ['pipe', 'pipe', 'pipe'], windowsHide: true });
    let output = '', error = '', failure;
    const abort = () => { failure = new Error('KCH_CANCELLED'); child.kill('SIGKILL'); };
    const timer = setTimeout(() => { failure = new Error('KCH_BRIDGE_TIMEOUT'); child.kill('SIGKILL'); }, config.timeoutMs);
    signal?.addEventListener('abort', abort, { once: true });
    child.stdout.on('data', chunk => {
      output += chunk;
      if (Buffer.byteLength(output) > config.maxOutputBytes) { failure = new Error('KCH_BRIDGE_OUTPUT_LIMIT'); child.kill('SIGKILL'); }
    });
    child.stderr.on('data', chunk => { error = (error + chunk).slice(-8192); });
    child.on('error', cause => { failure = cause; });
    child.stdin.on('error', cause => { failure = cause; });
    child.on('close', code => {
      clearTimeout(timer);
      signal?.removeEventListener('abort', abort);
      if (failure || code !== 0) { reject(failure ?? new Error(`KCH_BRIDGE_FAILURE:${error.trim()}`)); return; }
      try { accept(JSON.parse(output)); } catch (cause) { reject(cause); }
    });
    child.stdin.end(request(config, action, payload));
  });
}

function identity(ctx, config, exec) {
  if (!exec.agent || ctx.agents.get(exec.agent.id) !== exec.agent) throw new Error('KCH_EXACT_LIVE_AGENT_REQUIRED');
  const cwd = exec.agent.options?.cwd;
  if (typeof cwd !== 'string' || !isAbsolute(cwd) || realpathSync(cwd) !== config.workspaceRoot) throw new Error('KCH_WORKSPACE_BINDING_REQUIRED');
  return `${config.namespace}:${exec.agent.id}`;
}

function mapCall(ctx, config, exec) {
  const session = identity(ctx, config, exec);
  if (!Object.hasOwn(mappedNames, exec.name)) throw new Error(`KCH_UNMAPPED_TOOL:${exec.name}`);
  const args = exec.arguments;
  if (!args || typeof args !== 'object' || Array.isArray(args)) throw new Error('KCH_OBJECT_ARGUMENTS_REQUIRED');
  let cwd = config.workspaceRoot;
  if (exec.name === 'bash') {
    if (typeof args.command !== 'string') throw new Error('KCH_COMMAND_REQUIRED');
    if (args.workdir !== undefined) {
      if (typeof args.workdir !== 'string') throw new Error('KCH_WORKDIR_INVALID');
      cwd = realpathSync(resolve(cwd, args.workdir));
    }
  } else if (typeof args.file_path !== 'string') {
    throw new Error('KCH_FILE_PATH_REQUIRED');
  }
  if (!within(config.workspaceRoot, cwd)) throw new Error('KCH_WORKSPACE_ESCAPE');
  // Control files cannot be changed by native file tools. Shell is separately
  // tool-locked; only an exact, single-use native authorization can admit it.
  if (exec.name === 'write' || exec.name === 'edit') {
    let target = resolve(cwd, args.file_path);
    try { target = realpathSync(target); } catch {
      target = resolve(realpathSync(dirname(target)), target.split(sep).at(-1));
    }
    if (!within(config.workspaceRoot, target)) throw new Error('KCH_WORKSPACE_ESCAPE');
    if ([config.nativeRoot, config.dataDir, directory].some(root => within(root, target))) throw new Error('KCH_CONTROL_PATH_PROTECTED');
  }
  return {
    hook_event_name: 'PreToolUse', session_id: session, tool_use_id: String(exec.callId),
    tool_name: mappedNames[exec.name], tool_input: args, cwd,
    dsh_tool_name: exec.name, dsh_root_call_id: String(exec.rootCallId),
  };
}

/** Install in a DSH profile; all authority decisions remain in native KCH. */
export async function apply(ctx, input) {
  const config = validateConfig(input);
  const probe = invokeSync(config, 'probe');
  if (!probe.locksEnabled || !probe.chainValid) throw new Error('KCH_LOCKS_OR_LEDGER_NOT_READY');
  const decisions = new Map();
  let receiptFailure;
  const health = { lastReceipt: null, receipts: 0, get failure() { return receiptFailure ?? null; } };
  ctx.provide('kchDeepSeek', health);

  ctx.tools.guard(exec => {
    if (receiptFailure) return `KCH_RECEIPT_FAILURE:${receiptFailure}`;
    try { identity(ctx, config, exec); } catch (cause) { return cause.message; }
    const admitted = decisions.get(exec.token);
    if (!admitted || admitted.agent !== exec.agent || admitted.callId !== exec.callId) return 'KCH_NATIVE_DECISION_MISSING';
    return admitted.allowed ? undefined : admitted.reason;
  });

  ctx.on('tools/pre-execute', async (exec, next) => {
    const attempt = randomUUID();
    try {
      if (receiptFailure) throw new Error(`KCH_RECEIPT_FAILURE:${receiptFailure}`);
      const payload = mapCall(ctx, config, exec);
      payload.dsh_attempt_id = attempt;
      const result = await invoke(config, 'pre', payload, exec.signal);
      if (typeof result.allowed !== 'boolean') throw new Error('KCH_INVALID_NATIVE_DECISION');
      const allowed = result.allowed && !exec.signal.aborted;
      decisions.set(exec.token, { agent: exec.agent, callId: exec.callId, payload, attempt, allowed, reason: result.reason || 'KCH_NATIVE_DENIED' });
      if (!allowed) return { kind: 'deny', reason: result.reason || 'KCH_NATIVE_DENIED' };
      return next();
    } catch (cause) {
      const reason = `KCH_ADMISSION_FAILURE:${cause.message}`;
      decisions.set(exec.token, { agent: exec.agent, callId: exec.callId, attempt, allowed: false, reason });
      return { kind: 'deny', reason };
    }
  });

  // DSH final outcome notification is synchronous. Persist that exact frozen
  // outcome before returning; never treat a mutable post-execute result as final.
  ctx.on('tools/result', (exec, result) => {
    const admitted = decisions.get(exec.token);
    try {
      const receipt = invokeSync(config, 'receipt', {
        session_id: admitted?.payload?.session_id ?? null,
        dsh_session_id: exec.agent?.id ?? null, tool_use_id: String(exec.callId),
        dsh_attempt_id: admitted?.attempt ?? null, tool_name: exec.name,
        tool_input: exec.arguments, admission: admitted ? { allowed: admitted.allowed, reason: admitted.allowed ? null : admitted.reason } : { allowed: false, reason: 'KCH_NATIVE_DECISION_MISSING' },
        tool_response: result,
      });
      if (!receipt.recorded || typeof receipt.eventHash !== 'string') throw new Error('KCH_INVALID_RECEIPT');
      health.lastReceipt = receipt.eventHash;
      health.receipts += 1;
    } catch (cause) { receiptFailure = cause.message; }
    finally { decisions.delete(exec.token); }
  });
  ctx.effect(() => () => { decisions.clear(); });
}
