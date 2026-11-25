const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const elements=new Map();
function element(id){if(!elements.has(id))elements.set(id,{value:'',textContent:'',innerHTML:'',hidden:false,open:false,disabled:false,querySelectorAll:()=>[],getAttribute:()=>null,setAttribute:()=>{}});return elements.get(id)}
let response,requests=[];
class FormDataStub{constructor(){this.values={}}append(k,v){this.values[k]=v}entries(){return Object.entries(this.values)}}
const context=vm.createContext({document:{getElementById:id=>['reportForm','cropCanvas'].includes(id)?null:element(id),querySelectorAll:()=>[]},location:{hash:'#search'},FormData:FormDataStub,URL:{revokeObjectURL(){}},Date,Error,Number,String,Map,CampusUI:{words:value=>value},fetch:async(url,options)=>{requests.push({url,options});return {ok:true,json:async()=>response}}});
const source=fs.readFileSync('frontend/app.js','utf8');vm.runInContext(source.slice(0,source.indexOf("$('logout').onclick=")),context);
const run=code=>vm.runInContext(code,context),tick=()=>new Promise(setImmediate);
(async()=>{
  await run('render()');assert.match(element('view').innerHTML,/Log in to continue/);
  run("user={id:'seeker'};setupEditor=()=>{};selectPhoto=i=>{active=photos[i]}");
  context.location.hash='#report/LOST';await run('render()');assert.equal(context.location.hash,'search');
  context.location.hash='#search';await run('render()');assert.match(element('view').innerHTML,/Search found items by image/);assert.match(element('view').innerHTML,/<select id="searchCategory">/);assert.match(element('view').innerHTML,/<option value="other">/);
  run("loadPhoto=async file=>({file,url:'blob:query',box:null,confirmed:true})");
  element('searchPhoto').onchange({target:{files:['fixture-photo']}});await tick();
  element('searchCategory').value='bottle';element('searchText').value='Library';
  response={results:[{item_id:'found',image_url:'/api/v1/images/photo',title:'<private test>',location:'Library',event_date:'2026-11-24',rank:1,crop:[0,0,1,1],category_note:'Category is ambiguous'}],total_reports:1,searched_photos:2,elapsed_ms:100,next_offset:null,notice:'Not verified identity'};
  element('imageSearchForm').onsubmit({preventDefault(){}});await tick();
  assert.equal(requests.length,1);assert.equal(requests[0].url,'/api/v1/found/search-image');
  assert.equal(requests[0].options.body.values.category,'bottle');assert.equal(requests[0].options.body.values.photo,'fixture-photo');
  assert.equal(requests[0].options.body.values.strict_filters,'false');
  assert.match(element('imageSearchResults').innerHTML,/&lt;private test&gt;/);assert.match(element('imageSearchResults').innerHTML,/#item\/found/);
  assert.equal(run('comparisonPairs[0][0].url'),'blob:query');assert.equal(run('comparisonPairs[0][1].url'),'/api/v1/images/photo');
  context.location.hash='#privacy';await run('render()');context.location.hash='#search';await run('render()');
  assert.match(element('imageSearchResults').innerHTML,/Inspect report/);assert.equal(run('photos.length'),1);
  element('strictSearchFilters').checked=true;
  response={results:[],total_reports:0,searched_photos:0,elapsed_ms:0,next_offset:null,available_reports:1,available_photos:1,applied_filters:{category:'bottle',q:'Library'},empty_reason:'filters',notice:'No filtered matches'};
  element('imageSearchForm').onsubmit({preventDefault(){}});await tick();assert.match(element('imageSearchResults').innerHTML,/filters excluded them/);assert.match(element('imageSearchResults').innerHTML,/Search all found reports/);
  response={...response,empty_reason:null,total_reports:1,searched_photos:1,results:[]};element('searchAllFound').onclick();await tick();assert.equal(requests.at(-1).options.body.values.category,'');assert.equal(requests.at(-1).options.body.values.q,'');
  assert.equal(requests.at(-1).options.body.values.strict_filters,'false');
  element('continueLost').onclick();assert.equal(context.location.hash,'report/LOST/publish');assert.equal(run('reportDraft.photos[0].file'),'fixture-photo');assert.equal(run('imageSearchDraft'),null);
  assert(requests.every(r=>r.url!='/api/v1/items'));
  console.log('Image search: login, search-first lost flow, private upload, ranked report inspection, comparison, retained results and explicit draft handoff passed.');
})().catch(error=>{console.error(error);process.exitCode=1});
