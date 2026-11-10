const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const status={textContent:''};let response,request,controlsCalled=0;
const context=vm.createContext({document:{getElementById:()=>status},FormData,URL,Date,Error,Number,String,
  fetch:async(url,options)=>{request={url,options};if(response instanceof Error)throw response;return response},
  controls:()=>controlsCalled++});
const source=fs.readFileSync('frontend/app.js','utf8');vm.runInContext(source.slice(0,source.indexOf('function heading')),context);
(async()=>{
  response={ok:true,json:async()=>({ok:true})};
  vm.runInContext("csrf='fixture-csrf'",context);await vm.runInContext("api('/auth/profile',{method:'PATCH',body:{display_name:'Test'}})",context);
  assert.equal(request.options.headers['X-CSRF-Token'],'fixture-csrf');assert.equal(request.options.credentials,'same-origin');
  response=new Error('internal network detail');await assert.rejects(vm.runInContext("api('/items')",context),/Connection interrupted/);
  response={ok:false,json:async()=>{throw Error('proxy HTML')}};await assert.rejects(vm.runInContext("api('/items')",context),/temporarily unavailable/);
  const buttons=[{disabled:false},{disabled:true}],attrs={};const form={querySelectorAll:()=>buttons,getAttribute:k=>attrs[k],setAttribute:(k,v)=>attrs[k]=v};
  context.testForm=form;let release;context.action=()=>new Promise(r=>release=r);
  const saving=vm.runInContext('submit(testForm,action)',context);assert.equal(attrs['aria-busy'],'true');assert(buttons.every(b=>b.disabled));
  await vm.runInContext('submit(testForm,()=>{throw Error("duplicate submission")})',context);
  release();await saving;assert.equal(attrs['aria-busy'],'false');assert.deepEqual(buttons.map(b=>b.disabled),[false,true]);assert.equal(controlsCalled,1);
  assert.equal(vm.runInContext('esc("<img onerror=alert(1)>")',context),'&lt;img onerror=alert(1)&gt;');
  // A late rejection must not overwrite the status on a newer route.
  context.action=()=>new Promise((resolve,reject)=>release=reject);
  const stale=vm.runInContext('submit(testForm,action)',context);
  vm.runInContext('routeSequence++',context);status.textContent='New page';
  release(new Error('Old page failed'));await stale;
  assert.equal(status.textContent,'New page');
  // Disabled fields are omitted by FormData during submission. Preserve the
  // captured draft when a refresh warning is cancelled while upload is busy.
  vm.runInContext("user={id:'student'};reportDraft={fields:{title:'Retained'}};busy=true;captureDraft()",context);
  assert.equal(vm.runInContext('reportDraft.fields.title',context),'Retained');
  console.log('Platform CSRF, network recovery, busy state, duplicate submission and escaped text checks passed.');
})().catch(error=>{console.error(error);process.exitCode=1});
