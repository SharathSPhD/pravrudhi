'use strict';
const {discoverEngine, freePort} = require('./core');
const {createApiClient} = require('./api');
function loopbackOrigin(value) {
  try {
    const url = new URL(value);
    if (url.protocol !== 'http:' || !['127.0.0.1','localhost','[::1]'].includes(url.hostname) || url.username || url.password) return null;
    return url.origin;
  } catch { return null; }
}
async function selectConnection({candidates = [], discover = discoverEngine, allocate = freePort,
  health = origin => createApiClient(()=>origin,{timeout:1000}).health()} = {}) {
  for (const origin of new Set(candidates.map(loopbackOrigin).filter(Boolean))) {
    try { if ((await health(origin))?.ok === true) return {attached:true,origin,binary:await discover()}; } catch { /* Try the next installed endpoint. */ }
  }
  const binary = await discover();
  if (!binary) throw new Error('Connect an installed engine to get started.');
  return {attached:false,binary,origin:`http://127.0.0.1:${await allocate()}`};
}
function defaultWorkspace({env, saved, binary, home = require('node:os').homedir(), exists = require('node:fs').existsSync} = {}) {
  const path = require('node:path');
  if (env || saved) return path.resolve(env || saved);
  if (binary) {
    const project = path.resolve(path.dirname(binary),'../..');
    if (exists(path.join(project,'app/frontend/out/index.html'))) return project;
  }
  return path.resolve(home);
}
module.exports = {selectConnection, loopbackOrigin, defaultWorkspace};
