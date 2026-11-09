// Build from an allowlisted staging directory: no local .env, exports or server proxy.
import { cp, mkdir, rm, symlink, writeFile } from 'node:fs/promises';
import { spawnSync } from 'node:child_process';
import path from 'node:path';
const root = process.cwd(), stage = path.join(root, '.build-static');
await rm(stage, { recursive: true, force: true });
await mkdir(stage, { recursive: true });
for (const name of ['app', 'components', 'lib', 'package.json', 'tsconfig.json', 'next-env.d.ts']) {
  await cp(path.join(root,name), path.join(stage,name), {recursive:true});
}
await rm(path.join(stage,'app/api'), { recursive:true, force:true });
await symlink(path.join(root,'node_modules'), path.join(stage,'node_modules'), 'dir');
await writeFile(path.join(stage,'next.config.mjs'), 'export default { output: "export", poweredByHeader: false, images: {unoptimized: true} };\n');
const result = spawnSync(process.execPath, [path.join(root,'node_modules/next/dist/bin/next'), 'build', stage, '--webpack'], {stdio:'inherit',env:{...process.env,NODE_ENV:'production'}});
if(result.status !== 0) process.exit(result.status || 1);
await rm(path.join(root,'out'), { recursive:true, force:true });
await cp(path.join(stage,'out'), path.join(root,'out'), {recursive:true});
console.log('Static frontend ready in out/. No server proxy or local secrets included.');
