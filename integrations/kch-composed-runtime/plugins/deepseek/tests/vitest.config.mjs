import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { dirname, resolve } from 'node:path';
if (!process.env.DSH_SOURCE) throw new Error('DSH_SOURCE must name the pinned upstream checkout');
const upstream = resolve(process.env.DSH_SOURCE);
const require = createRequire(resolve(upstream, 'package.json'));
const { defineConfig } = await import(pathToFileURL(require.resolve('vitest/config')));
const { default: tsconfigPaths } = await import(pathToFileURL(require.resolve('vite-tsconfig-paths')));
const ts = require('typescript');
const parsed = ts.readConfigFile(resolve(upstream, 'tsconfig.base.json'), ts.sys.readFile).config;
const aliases = Object.entries(parsed.compilerOptions.paths)
  .filter(([key]) => !key.includes('*'))
  .map(([key, paths]) => ({ find: new RegExp(`^${key.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}$`), replacement: resolve(upstream, paths[0]) }));
const { standardDecoratorPlugin, vitestExecArgv } = await import(pathToFileURL(resolve(upstream, 'vitest.shared.ts')));
const tests = dirname(fileURLToPath(import.meta.url));
export default defineConfig({
  root: upstream,
  resolve: { alias: aliases },
  plugins: [standardDecoratorPlugin(), tsconfigPaths({ projects: [resolve(upstream, 'tsconfig.base.json')] })],
  test: { include: [resolve(tests, 'integration.spec.ts')], testTimeout: 30000, hookTimeout: 30000, execArgv: vitestExecArgv },
});
