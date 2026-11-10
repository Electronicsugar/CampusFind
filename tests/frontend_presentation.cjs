const assert=require('node:assert/strict');
const ui=require('../frontend/app-ui.js');
assert.match(ui.claimNext({status:'APPROVED',is_claimant:true}),/physically receive/);
assert.match(ui.claimNext({status:'APPROVED',is_claimant:false}),/wait for the claimant/);
assert.match(ui.claimNext({status:'PENDING',is_claimant:false}),/private evidence/);
assert.match(ui.claimNext({status:'RETURNED'}),/No further action/);
assert.match(ui.claimNext({status:'APPROVED',unavailable:true}),/removed/);
assert.equal(ui.matchStatus({status:'PENDING'}).style,'pending');
assert.equal(ui.matchStatus({status:'FAILED'}).style,'failed');
assert.equal(ui.matchStatus({status:'DONE'}).style,'done');
assert.equal(ui.matchStatus({status:'unexpected'}).title,'Matching status unavailable');
assert.match(ui.matchStatus({status:'DONE'}).copy,/does not verify identity/);
assert.deepEqual(ui.summary([
  {kind:'LOST',state:'OPEN'}, {kind:'FOUND',state:'MATCH_SUGGESTED'},
  {kind:'LOST',state:'RETURNED'}, {kind:'FOUND',state:'CLOSED'},
  {kind:'LOST',state:'CLAIM_PENDING'}
],[{status:'PENDING'},{status:'PENDING',unavailable:true},{status:'APPROVED'}]).map(x=>x.value),[2,1,1,1]);
assert.deepEqual(ui.summary([],[]).map(x=>x.value),[0,0,0,0]);
assert.equal(ui.escape('<img onerror="bad">'),'&lt;img onerror=&quot;bad&quot;&gt;');
assert.equal(ui.words('MATCH_SUGGESTED'),'Match suggested');
console.log('Presentation: honest match states, role-specific claim guidance, scoped counts and escaping passed.');
