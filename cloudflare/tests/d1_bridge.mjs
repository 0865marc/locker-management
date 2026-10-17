/** Test-only transport to official Miniflare/workerd D1. Never shipped. */
import { Miniflare } from 'miniflare';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const ownsState = process.argv[2] === undefined;
const state = process.argv[2] ?? await mkdtemp(join(tmpdir(), 'locker-native-d1-'));
const script = `
const invalid = () => { throw new Error('Invalid test bridge request'); };
function statement(db, item) {
  if (!item || typeof item.sql !== 'string' || !item.sql.length || item.sql.length > 262144 ||
      !Array.isArray(item.params) || item.params.length > 100 ||
      item.params.some(x => x !== null && typeof x !== 'string' &&
        !(typeof x === 'number' && Number.isFinite(x) &&
          (!Number.isInteger(x) || Number.isSafeInteger(x))))) invalid();
  return db.prepare(item.sql).bind(...item.params);
}
export default {
 async fetch(request, env) {
  try {
   if (request.method !== 'POST' || new URL(request.url).pathname !== '/')
    return Response.json({error:'Invalid test bridge route'}, {status:404});
   if (!request.body) invalid();
   const reader = request.body.getReader();
   const decoder = new TextDecoder();
   let bytes = 0;
   let text = '';
   while (true) {
    const part = await reader.read();
    if (part.done) break;
    bytes += part.value.byteLength;
    if (bytes > 4194304) { await reader.cancel(); invalid(); }
    text += decoder.decode(part.value, {stream:true});
   }
   text += decoder.decode();
   const body = JSON.parse(text);
   let result;
   if (body.op === 'batch') {
    if (!Array.isArray(body.statements) || body.statements.length < 1 || body.statements.length > 100) invalid();
    result = await env.DB.batch(body.statements.map(x => statement(env.DB, x)));
   } else if (body.op === 'exec') {
    if (typeof body.sql !== 'string' || !body.sql.length || body.sql.length > 262144) invalid();
    result = await env.DB.exec(body.sql);
   } else if (['first','all','run'].includes(body.op)) {
    result = await statement(env.DB, body.statement)[body.op]();
   } else invalid();
   return Response.json({result});
  } catch (error) {
   return Response.json({error:String(error)}, {status:400});
  }
 }
};`;
let mf;
try {
mf = new Miniflare({
  host: '127.0.0.1', port: 0, resourcePersistencePath: state,
  telemetry: {enabled: false}, logRequests: false,
  workers: [{config: {name: 'd1-test', compatibilityDate: '2026-04-01',
    manifest: {mainModule: 'worker.mjs', modules: {'worker.mjs': {type:'esm', contents:script}}},
    env: {DB: {type: 'd1', id: 'native-d1-test'}},
  }}],
});
} catch (error) {
  if (ownsState) await rm(state, {recursive:true, force:true});
  throw error;
}
let closing = false;
async function close() {
  if (closing) return;
  closing = true;
  await mf.dispose();
  if (ownsState) await rm(state, {recursive:true, force:true});
}
process.on('SIGTERM', () => { void close().then(() => process.exit(0)); });
process.on('SIGINT', () => { void close().then(() => process.exit(0)); });
process.stdin.resume();
process.stdin.on('end', () => { void close().then(() => process.exit(0)); });
try {
  const url = await mf.ready;
  process.stdout.write(JSON.stringify({url:String(url)}) + '\n');
} catch (error) {
  await close();
  throw error;
}
