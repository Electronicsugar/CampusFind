// Suggestions are per-image drafts. Matching uses only explicitly accepted boxes.
function renderSuggestions(){
  const panel=$('suggestions');panel.replaceChildren();
  $('suggestionNote').textContent=active?.proposalNote||'';
  if(!active)return;
  for(const [index,proposal] of (active.proposals||[]).entries()){
    const button=document.createElement('button');button.className='secondary';button.type='button';
    button.textContent='Preview '+(index+1)+': '+proposal.label;
    button.onclick=()=>{active.draft=proposal.box.slice();active.draftIndex=index;renderSuggestions();draw();controls()};
    button.setAttribute('aria-pressed',String(active.draftIndex===index));panel.append(button);
  }
  $('acceptSuggestion').hidden=!active.draft;
  $('rejectSuggestion').hidden=!(active.proposals||[]).length;
}

function bindDetection(){
if($('suggest'))$('suggest').onclick=async()=>{
  const target=active;if(!target)return;
  busy=true;controls();message('Finding object suggestions locally. The first request loads the detector; you can review every box before applying it.');
  const form=new FormData();form.append('image',target.file);form.append('prompt',$('objectHint').value.trim());form.append('model',$('detectorModel').value);
  const controller=new AbortController();const timeout=setTimeout(()=>controller.abort(),120000);
  try{
    const response=await fetch('/api/suggest-crops',{method:'POST',body:form,signal:controller.signal,headers:typeof cropRequestHeaders==='function'?cropRequestHeaders():{}});
    const data=await response.json();if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:'Could not suggest objects. Crop manually.');
    if(!Array.isArray(data.proposals))throw Error('Invalid detector response. Crop manually.');
    // A new request clears only suggestion drafts, never an accepted selection.
    target.proposals=data.proposals;target.proposalNote=data.note;target.draft=null;target.draftIndex=null;
    if(active===target&&$('suggest')){renderSuggestions();draw();message(data.note+' Analysis took '+(data.elapsed_ms/1000).toFixed(1)+' seconds.')}
  }catch(error){if(active===target)message(error.name==='AbortError'?'Detection timed out. You can draw a crop manually.':error.message)}
  finally{clearTimeout(timeout);if(active===target){busy=false;controls()}}
};
if($('acceptSuggestion'))$('acceptSuggestion').onclick=()=>{
  if(!active?.draft)return;
  const box=active.draft.slice();active.draft=null;active.draftIndex=null;
  setBox(box);renderSuggestions();message('Suggested crop accepted. Adjust it by dragging a new box or using the crop fields.');
};
if($('rejectSuggestion'))$('rejectSuggestion').onclick=()=>{
  if(!active)return;active.proposals=[];active.proposalNote='';active.draft=null;active.draftIndex=null;
  renderSuggestions();draw();controls();message('Suggestions dismissed. Your previous selection is unchanged. Draw a crop or explicitly choose Use full image.');
};

}
bindDetection();
