const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
let listener,focused=0;
const dialog={open:false,returnValue:'',addEventListener:(event,fn)=>{listener=fn},
  showModal(){this.open=true},close(value=''){this.open=false;this.returnValue=value;listener()}};
const context=vm.createContext({Promise,document:{activeElement:{isConnected:true,focus:()=>focused++}},$:()=>dialog});
const source=fs.readFileSync('frontend/app.js','utf8');
vm.runInContext(source.slice(source.indexOf('function confirmHandover'),source.indexOf('async function render')),context);
(async()=>{
  let result=vm.runInContext('confirmHandover()',context);
  assert(dialog.open);assert.equal(await vm.runInContext('confirmHandover()',context),false);
  dialog.close('cancel');assert.equal(await result,false);assert.equal(focused,1);
  result=vm.runInContext('confirmHandover()',context);dialog.close('confirm');
  assert.equal(await result,true);assert.equal(focused,2);
  result=vm.runInContext('confirmHandover()',context);dialog.close();
  assert.equal(await result,false); // Escape/dismissal never confirms receipt.
  console.log('Handover: explicit confirmation, cancellation, duplicate guard and focus restoration passed.');
})().catch(error=>{console.error(error);process.exitCode=1});
