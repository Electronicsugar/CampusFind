const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const elements=new Map();
function element(id){if(!elements.has(id))elements.set(id,{textContent:'',innerHTML:'',hidden:false,open:false,disabled:false,checked:false,querySelectorAll:()=>[],getAttribute:()=>null,setAttribute:()=>{}});return elements.get(id)}
let request,response;
class FormDataStub{constructor(form){this.data=form.data}entries(){return Object.entries(this.data)}}
const context=vm.createContext({document:{getElementById:id=>['reportForm','cropCanvas'].includes(id)?null:element(id),querySelectorAll:()=>[]},location:{hash:'#login'},FormData:FormDataStub,URL,Date,Error,Number,String,Map,
  CampusUI:{},fetch:async(url,options)=>{request={url,options};return {ok:true,json:async()=>response}}});
const source=fs.readFileSync('frontend/app.js','utf8');vm.runInContext(source.slice(0,source.indexOf("$('logout').onclick=")),context);
const run=code=>vm.runInContext(code,context),tick=()=>new Promise(setImmediate);
const codes=['12345678-ABCDEF12-12345678-ABCDEF12'];
(async()=>{
  assert.doesNotMatch(run('authPage(false)'),/href="#register"/);
  assert.match(run('authPage(false)'),/href="#recover"/);
  run('registrationOpen=true');assert.match(run('authPage(false)'),/href="#register"/);
  assert.match(run('authPage(true)'),/minlength="6" maxlength="12"/);
  assert.match(run('authPage(true)'),/pattern="\(\?=.*\[A-Za-z\]\)/);
  assert.match(run('authPage(false)'),/maxlength="128"/);
  context.location.hash='#register';await run('render()');
  response={user:{id:'test'},csrf:'csrf',recovery_codes:codes};element('authForm').data={email:'test@example.edu',password:'Test123!',display_name:'Test'};
  element('authForm').onsubmit({preventDefault(){},target:element('authForm')});await tick();
  assert.equal(context.location.hash,'recovery-codes');assert.equal(request.url,'/api/v1/auth/register');
  context.location.hash='#recovery-codes';await run('render()');
  assert.match(element('view').innerHTML,/Save your recovery codes/);
  element('finishRecovery').onclick();assert.equal(context.location.hash,'#recovery-codes');
  element('savedCodes').checked=true;element('savedCodes').onchange();assert.equal(element('finishRecovery').disabled,false);
  element('finishRecovery').onclick();assert.equal(context.location.hash,'dashboard');assert.equal(run('recoveryBundle'),null);
  context.location.hash='#recover';await run('render()');
  const form=element('recoveryForm');form.data={email:'test@example.edu',password:'Reset123!',confirm_password:'Other123!',recovery_code:codes[0]};request=null;
  form.onsubmit({preventDefault(){},target:form});await tick();assert.equal(request,null);assert.match(element('status').textContent,/must match/);
  form.data.confirm_password=form.data.password;response={ok:true,recovery_codes:codes};
  form.onsubmit({preventDefault(){},target:form});await tick();
  assert.equal(request.url,'/api/v1/auth/reset-password');assert(!JSON.parse(request.options.body).confirm_password);
  assert.equal(run('user'),null);assert.equal(run('recoveryBundle.next'),'login');
  assert(!context.location.hash.includes(codes[0]));
  context.location.hash='#login';await run('render()');assert.equal(run('recoveryBundle'),null);
  console.log('Signup, recovery-code acknowledgment, reset confirmation, password bounds and ephemeral code handling passed.');
})().catch(error=>{console.error(error);process.exitCode=1});
