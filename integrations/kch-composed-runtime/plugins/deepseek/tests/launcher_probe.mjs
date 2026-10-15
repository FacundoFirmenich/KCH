/** Real launcher probe: runs no model and substitutes no DSH runtime. */
import { readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
export const name = 'kch-launcher-probe';
export const inject = ['kchDeepSeek', 'agentLoop', 'tools'];
export async function apply(ctx, config) {
  const agent = await ctx.agentLoop.create('kch-launcher-proof', { cwd: config.workspace });
  const execute = (callId, name, arguments_) => ctx.tools.execute({
    callId, name, arguments: arguments_, agent, signal: new AbortController().signal,
  });
  const original = readFileSync(config.protectedPath, 'utf8');
  const read = await execute('launcher-read', 'read', { file_path: config.protectedPath });
  const denied = await execute('launcher-write-denied', 'write', {
    file_path: config.protectedPath, content: 'This explicit adversarial overwrite must be denied.',
  });
  const after = readFileSync(config.protectedPath, 'utf8');
  const health = ctx.get('kchDeepSeek');
  const result = {
    pluginActive: !!health, read, denied, sourceUnchanged: after === original,
    receipts: health.receipts, lastReceipt: health.lastReceipt, failure: health.failure,
    modelTurnSubmitted: false, method: 'Real SDK launcher; idle registered Agent; real ToolRuntime and native file tool.',
  };
  if (read.isError || !denied.isError || !JSON.stringify(denied).includes('KCH_BLOCKED_EXACT_USER_AUTHORIZATION_REQUIRED')
      || !result.sourceUnchanged || result.receipts !== 2 || result.failure) {
    throw new Error(`KCH_LAUNCHER_PROBE_FAILED:${JSON.stringify(result)}`);
  }
  writeFileSync(resolve(config.output), JSON.stringify(result, null, 2) + '\n', { flag: 'wx' });
}
