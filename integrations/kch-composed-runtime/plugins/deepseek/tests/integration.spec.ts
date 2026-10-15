import { afterEach, describe, expect, it } from 'vitest';
import { Context } from '@deepseek-ai/cordis';
import LlmRuntime, { ToolCallId } from '@deepseek-ai/dsh-llm';
import SessionStore, { SessionId } from '@deepseek-ai/dsh-session';
import SessionProjectionRegistry from '@deepseek-ai/dsh-session-projection';
import SystemPrompt from '@deepseek-ai/dsh-system-prompt';
import ToolRuntime from '@deepseek-ai/dsh-tools';
import AgentRegistry from '@deepseek-ai/dsh-agent';
import AgentLoop from '@deepseek-ai/dsh-agent-loop';
import LocalFileSystem from '@deepseek-ai/dsh-fs-local';
import * as FileTools from '@deepseek-ai/dsh-tool-fs';
import * as KchPlugin from '../index.mjs';
import { spawnSync } from 'node:child_process';
import { mkdtemp, mkdir, readFile, writeFile, rm, symlink } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const pluginRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const repo = resolve(pluginRoot, '../../../..');
const nativeRoot = resolve(repo, 'construct_successors/KCH_ALL_IN_ONE_0.11.33_STUDIO_0.3.16_AIO2/vendor/kch-native-r33-0.11.33');
const contexts: Context[] = [];
const directories: string[] = [];

function native(config, code: string, values = {}) {
  const result = spawnSync('python3', ['-c', `import sys,os,json\nr=json.load(sys.stdin)\nsys.path.insert(0,r['nativeRoot']+'/scripts')\nos.environ['KCH_NATIVE_DATA']=r['dataDir']\nimport kch_native_state as s\ndb=s.connect()\n${code}\ndb.close()`], {
    input: JSON.stringify({ ...config, ...values }), encoding: 'utf8',
  });
  if (result.status !== 0) throw new Error(result.stderr);
  return result.stdout.trim() ? JSON.parse(result.stdout) : undefined;
}

async function harness({ enabled = true, mount = true } = {}) {
  const root = await mkdtemp(resolve(tmpdir(), 'kch-dsh-real-'));
  directories.push(root);
  const workspaceRoot = resolve(root, 'workspace'), dataDir = resolve(root, 'native');
  await mkdir(workspaceRoot); await mkdir(dataDir);
  const protectedPath = resolve(workspaceRoot, 'protected.txt');
  await writeFile(protectedPath, 'original protected content\n');
  const config = { nativeRoot, workspaceRoot, dataDir, namespace: 'integration-proof' };
  native(config, "s.set_setting(db,'locks_enabled','true' if r['enabled'] else 'false')\ndb.execute('INSERT INTO locks(id,kind,pattern,created_at) VALUES(?,?,?,?)', ('protected','EXACT',s.normalize_file(r['protectedPath'],r['workspaceRoot']),s.utc_now()))\ndb.commit()", { enabled, protectedPath });
  const ctx = new Context(); contexts.push(ctx);
  await ctx.plugin(LlmRuntime);
  await ctx.plugin(SessionStore);
  await ctx.plugin(SessionProjectionRegistry);
  await ctx.plugin(SystemPrompt);
  await ctx.plugin(ToolRuntime);
  await ctx.plugin(AgentRegistry);
  await ctx.plugin(AgentLoop, { agents: [] });
  await ctx.plugin(LocalFileSystem, { cwd: workspaceRoot });
  await ctx.plugin(FileTools);
  if (mount) await ctx.plugin(KchPlugin, config);
  // Real upstream ReactLoopAgent, deliberately idle. No provider adapter,
  // canned model outputs, credentials, or model request is used.
  const agent = await ctx.agentLoop.create(SessionId('proof-session'), { cwd: workspaceRoot });
  let call = 0;
  const execute = (name: string, args: object, owner = agent) => ctx.tools.execute({
    callId: ToolCallId(`actual-${++call}`), name, arguments: args, agent: owner,
    signal: new AbortController().signal,
  });
  return { ctx, agent, execute, config, protectedPath };
}

afterEach(async () => {
  for (const ctx of contexts.splice(0)) await ctx.fiber.dispose();
  for (const dir of directories.splice(0)) await rm(dir, { recursive: true, force: true });
});

describe('real KCH native policy inside real DSH tool pipeline', () => {
  it('reads a locked file, blocks overwrite/edit, performs an unprotected write, and verifies exact receipts', async () => {
    const h = await harness();
    const read = await h.execute('read', { file_path: h.protectedPath });
    expect(read.isError).not.toBe(true);
    expect(JSON.stringify(read)).toContain('original protected content');
    const write = await h.execute('write', { file_path: h.protectedPath, content: 'changed' });
    expect(write.isError).toBe(true);
    expect(JSON.stringify(write)).toContain('KCH_BLOCKED_EXACT_USER_AUTHORIZATION_REQUIRED');
    const edit = await h.execute('edit', { file_path: h.protectedPath, old_string: 'original', new_string: 'changed' });
    expect(edit.isError).toBe(true);
    expect(await readFile(h.protectedPath, 'utf8')).toBe('original protected content\n');
    const target = resolve(h.config.workspaceRoot, 'created.txt');
    const allowed = await h.execute('write', { file_path: target, content: 'Created by upstream dsh-tool-fs.\n' });
    expect(allowed.isError).not.toBe(true);
    expect(await readFile(target, 'utf8')).toBe('Created by upstream dsh-tool-fs.\n');
    const ledger = native(h.config, "valid,count=s.verify_chain(db)\nrows=[dict(x) for x in db.execute('SELECT event_name,payload_json FROM events ORDER BY id')]\nprint(json.dumps({'valid':valid,'count':count,'rows':rows}))");
    expect(ledger.valid).toBe(true);
    const receipts = ledger.rows.filter(row => row.event_name === 'DSHToolResult').map(row => JSON.parse(row.payload_json));
    expect(receipts).toHaveLength(4);
    expect(receipts.every(row => row.session_id === 'integration-proof:proof-session')).toBe(true);
    expect(receipts[1].tool_response).toEqual(write);
    expect(receipts[3].tool_response).toEqual(allowed);
    expect(h.ctx.get('kchDeepSeek').failure).toBe(null);
  });

  it('does not allow a later hook to turn native denial into permission', async () => {
    const h = await harness();
    h.ctx.on('tools/pre-execute', async (_exec, next) => { await next(); return { kind: 'allow' }; }, { prepend: true });
    const denied = await h.execute('write', { file_path: h.protectedPath, content: 'bypass' });
    expect(denied.isError).toBe(true);
    expect(JSON.stringify(denied)).toContain('KCH_BLOCKED_EXACT_USER_AUTHORIZATION_REQUIRED');
    expect(await readFile(h.protectedPath, 'utf8')).toBe('original protected content\n');
  });

  it('fails closed if an earlier hook skips KCH admission', async () => {
    const h = await harness();
    h.ctx.on('tools/pre-execute', async () => ({ kind: 'allow' }), { prepend: true });
    const denied = await h.execute('write', { file_path: h.protectedPath, content: 'bypass' });
    expect(denied.isError).toBe(true);
    expect(JSON.stringify(denied)).toContain('KCH_NATIVE_DECISION_MISSING');
    expect(await readFile(h.protectedPath, 'utf8')).toBe('original protected content\n');
  });

  it('resolves a real symlink alias before checking the native path lock', async () => {
    const h = await harness();
    const alias = resolve(h.config.workspaceRoot, 'alias.txt');
    await symlink(h.protectedPath, alias);
    const denied = await h.execute('edit', { file_path: alias, old_string: 'original', new_string: 'bypass' });
    expect(denied.isError).toBe(true);
    expect(JSON.stringify(denied)).toContain('KCH_BLOCKED_EXACT_USER_AUTHORIZATION_REQUIRED');
    expect(await readFile(h.protectedPath, 'utf8')).toBe('original protected content\n');
  });

  it('rejects a forged agent object even when its session id matches the live agent', async () => {
    const h = await harness();
    const denied = await h.execute('write', { file_path: h.protectedPath, content: 'bypass' }, { id: h.agent.id, options: h.agent.options });
    expect(denied.isError).toBe(true);
    expect(JSON.stringify(denied)).toContain('KCH_EXACT_LIVE_AGENT_REQUIRED');
    expect(await readFile(h.protectedPath, 'utf8')).toBe('original protected content\n');
  });

  it('refuses activation when native locks are disabled, without enabling them', async () => {
    const h = await harness({ enabled: false, mount: false });
    await expect(h.ctx.plugin(KchPlugin, h.config)).rejects.toThrow('KCH_LOCKS_OR_LEDGER_NOT_READY');
    expect(native(h.config, "print(json.dumps(s.setting(db,'locks_enabled')))" )).toBe('false');
  });

  it('blocks an alias of the actual upstream write tool until an explicit mapping exists', async () => {
    const h = await harness();
    h.ctx.tools.register({ ...h.ctx.tools.get('write'), name: 'read_disguised_writer' });
    const denied = await h.execute('read_disguised_writer', { file_path: h.protectedPath, content: 'bypass' });
    expect(denied.isError).toBe(true);
    expect(JSON.stringify(denied)).toContain('KCH_UNMAPPED_TOOL');
    expect(await readFile(h.protectedPath, 'utf8')).toBe('original protected content\n');
  });

  it('blocks direct tool dispatch without an agent and an actual agent without the workspace binding', async () => {
    const h = await harness();
    const direct = await h.ctx.tools.execute({ callId: ToolCallId('no-agent'), name: 'write', arguments: { file_path: h.protectedPath, content: 'bypass' }, signal: new AbortController().signal });
    expect(direct.isError).toBe(true);
    expect(JSON.stringify(direct)).toContain('KCH_EXACT_LIVE_AGENT_REQUIRED');
    const other = await h.ctx.agentLoop.create(SessionId('other-workspace'), { cwd: tmpdir() });
    const denied = await h.execute('write', { file_path: h.protectedPath, content: 'bypass' }, other);
    expect(denied.isError).toBe(true);
    expect(JSON.stringify(denied)).toContain('KCH_WORKSPACE_BINDING_REQUIRED');
    expect(await readFile(h.protectedPath, 'utf8')).toBe('original protected content\n');
  });

  it('blocks after native locks are disabled during a live installation', async () => {
    const h = await harness();
    native(h.config, "s.set_setting(db,'locks_enabled','false')");
    const denied = await h.execute('write', { file_path: h.protectedPath, content: 'bypass' });
    expect(denied.isError).toBe(true);
    expect(JSON.stringify(denied)).toContain('KCH_LOCKS_DISABLED');
    expect(await readFile(h.protectedPath, 'utf8')).toBe('original protected content\n');
  });

  it('prevents the upstream file tool from modifying the native control directory', async () => {
    const h = await harness();
    const controlAlias = resolve(h.config.workspaceRoot, 'native-state');
    await symlink(h.config.dataDir, controlAlias, 'dir');
    const denied = await h.execute('write', { file_path: resolve(controlAlias, 'control.txt'), content: 'bypass' });
    expect(denied.isError).toBe(true);
    expect(JSON.stringify(denied)).toMatch(/KCH_WORKSPACE_ESCAPE|KCH_CONTROL_PATH_PROTECTED/);
  });
});
