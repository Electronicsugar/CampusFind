const {spawnSync}=require('node:child_process'),fs=require('node:fs'),assert=require('node:assert/strict');
function build(url){return spawnSync(process.execPath,['scripts/build_vercel_frontend.mjs'],{env:{...process.env,CAMPUSFIND_BACKEND_URL:url},encoding:'utf8'})}
assert.equal(build('').status,0);
assert.match(fs.readFileSync('.vercel/output/static/index.html','utf8'),/backend is not connected/);
assert.equal(JSON.parse(fs.readFileSync('.vercel/output/config.json')).routes.find(r=>r.src.startsWith('/(api')).status,503);
for(const bad of ['http://backend.example','https://user:secret@backend.example','https://backend.example/path'])assert.notEqual(build(bad).status,0);
assert.equal(build('https://backend.example').status,0);
assert.doesNotMatch(fs.readFileSync('.vercel/output/static/index.html','utf8'),/backend is not connected/);
assert.equal(JSON.parse(fs.readFileSync('.vercel/output/config.json')).routes.find(r=>r.src.startsWith('/(api')).dest,'https://backend.example/$1');
assert(fs.existsSync('.vercel/output/static/detection.js'));
assert(!fs.existsSync('.vercel/output/static/.env'));
console.log('Vercel build: explicit offline status, HTTPS proxy validation, allowlisted frontend assets passed.');
