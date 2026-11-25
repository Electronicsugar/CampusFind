// Build Output API: publish only allowlisted frontend files, never Python data/secrets.
import {mkdir,readFile,writeFile,copyFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const output=path.join(root,'.vercel/output');
const {version}=JSON.parse(await readFile(path.join(root,'app-version.json'),'utf8'));
const appSource=await readFile(path.join(root,'frontend/app.js'),'utf8');
if(!appSource.includes("const APP_VERSION='"+version+"'"))throw Error('Frontend and release versions must match.');
const backend=(process.env.CAMPUSFIND_BACKEND_URL||'').trim();
if(backend){
  const url=new URL(backend);
  if(url.protocol!=='https:'||url.username||url.password||url.search||url.hash||url.pathname!=='/')throw Error('Backend must be an HTTPS origin without credentials or path.');
}
await mkdir(path.join(output,'static/assets'),{recursive:true});
for(const file of ['app.css','app.js','app-ui.js'])await copyFile(path.join(root,'frontend',file),path.join(output,'static/assets',file));
await copyFile(path.join(root,'frontend/detection.js'),path.join(output,'static/detection.js'));
let home=await readFile(path.join(root,'frontend/app.html'),'utf8');
if(!backend){
  home=home.replace('<main ', '<aside class="deployment-notice" role="status">Public preview: the backend is not connected yet. Accounts, reports, uploads and matching are currently unavailable.</aside><main ');
  await writeFile(path.join(output,'static/assets/deployment.css'),'.deployment-notice{padding:16px 24px;background:#fff4df;color:#684416;border-bottom:1px solid #dccba8;font:16px/1.5 system-ui}');
  home=home.replace('</head>','<link rel="stylesheet" href="/assets/deployment.css"></head>');
}
await writeFile(path.join(output,'static/index.html'),home);
for(const [route,file] of [['gallery','gallery.html'],['lab','index.html']])await writeFile(path.join(output,'static',route+'.html'),await readFile(path.join(root,'frontend',file)));
await writeFile(path.join(output,'static/backend-unavailable.json'),JSON.stringify({detail:'The public backend is not connected. Please try again after it is started.'}));
await writeFile(path.join(output,'static/app-version.json'),JSON.stringify({version}));
const routes=[
  {src:'/(?:|index\\.html|app|app-version\\.json|assets/(?:app\\.js|app-ui\\.js|app\\.css))',headers:{'Cache-Control':'no-store','X-CampusFind-Version':version},continue:true},
  {src:'/(.*)',headers:{'X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY','Referrer-Policy':'same-origin','Permissions-Policy':'camera=(), microphone=(), geolocation=()'},continue:true},
  {src:'/(?:|index\\.html|app)',headers:{'Content-Security-Policy':"default-src 'self'; img-src 'self' blob: data:; script-src 'self'; style-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"},continue:true},
  {src:'/(api(?:/.*)?|health(?:/.*)?)',dest:backend?backend.replace(/\/$/,'')+'/$1':'/backend-unavailable.json',...(backend?{}:{status:503}),headers:{'Cache-Control':'no-store'}},
  {src:'/(gallery|lab)',dest:'/$1.html'},
  {src:'/app',dest:'/index.html'},
  {handle:'filesystem'},
];
await writeFile(path.join(output,'config.json'),JSON.stringify({version:3,routes},null,2));
console.log('Built public frontend; backend '+(backend?'connected by HTTPS proxy':'unavailable (explicit preview notice)'));
