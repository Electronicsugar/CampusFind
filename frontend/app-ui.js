'use strict';
// Presentation helpers only. API authorization and match ordering stay authoritative.
const CampusUI = (() => {
  const escape = value => String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const words = value => String(value||'').toLowerCase().replaceAll('_',' ').replace(/^./,c=>c.toUpperCase());
  const states = {OPEN:'Open',MATCH_SUGGESTED:'Suggestions available',CLAIM_PENDING:'Handover in progress',RETURNED:'Returned',CLOSED:'Closed',PENDING:'Awaiting review',APPROVED:'Ready for handover',REJECTED:'Not approved',WITHDRAWN:'Withdrawn'};
  function claimNext(claim){
    if(claim.unavailable)return 'This report is no longer available. Private details have been removed.';
    const own=claim.is_claimant;
    return {PENDING:own?'The finder is reviewing your private evidence. You can withdraw this claim.':'Review the private evidence. Approve only when ownership details are convincing.',
      APPROVED:own?'Read the handover note. Confirm receipt only after you physically receive the item.':'The claim is approved. Arrange a safe handover and wait for the claimant to confirm receipt.',
      REJECTED:'This claim was not approved. Read the review note for details.',WITHDRAWN:'The claimant withdrew this request.',RETURNED:'The physical handover has been recorded. No further action is needed.'}[claim.status]||'Check the latest claim details below.';
  }
  function matchStatus(result){
    if(result.status==='PENDING')return {title:'Looking for potential matches',copy:'Your report is saved. Matching is queued or running. Refresh results shortly; you can safely leave this page.',style:'pending'};
    if(result.status==='FAILED')return {title:'Your report is saved. Matching needs attention.',copy:result.message||'Matching could not finish. Try again later or contact your campus coordinator.',style:'failed'};
    if(result.status==='DONE')return {title:'Matching finished',copy:'Inspect the suggestions below, including uncertain results. Similarity does not verify identity.',style:'done'};
    return {title:'Matching status unavailable',copy:'Refresh to check the latest status. Your report remains saved.',style:'pending'};
  }
  function summary(items,claims){
    const active=items.filter(i=>['OPEN','MATCH_SUGGESTED','CLAIM_PENDING'].includes(i.state));
    return [{label:'Active lost reports',value:active.filter(i=>i.kind==='LOST').length},
      {label:'Active found reports',value:active.filter(i=>i.kind==='FOUND').length},
      {label:'Reports with suggestions',value:items.filter(i=>i.state==='MATCH_SUGGESTED').length},
      {label:'Pending claims',value:claims.filter(c=>c.status==='PENDING'&&!c.unavailable).length}];
  }
  function home(){return `<section class="hero"><div class="hero-copy"><div class="eyebrow">A little care. A closer campus.</div><h1>Lost happens.<br><span>Let’s find a way back.</span></h1><p>From your favorite bottle to the keys you can’t leave without. Report a lost item, share a find, and help your campus reconnect.</p><div class="actions"><a class="button" href="#report/LOST">I Lost Something <span aria-hidden="true">↗</span></a><a class="button secondary" href="#report/FOUND">I Found Something</a></div><a class="browse-link" href="#browse">Browse Lost &amp; Found <span aria-hidden="true">→</span></a><p class="fine hero-note">Private evidence. Thoughtful handovers. People make the final call.</p></div><div class="hero-art" aria-hidden="true"><span class="art-kicker">EVERYDAY THINGS. REAL CONNECTIONS.</span><div class="illustrated-items"><div class="drawn-bottle"><i></i><span>cf.</span></div><div class="drawn-book"><span>notes<br>&amp; ideas</span></div><div class="drawn-keys">⌘</div></div><div class="art-caption"><span class="mini-mark">↗</span><div><strong>Someone’s small essential.</strong><span>A chance to make their day.</span></div></div></div></section><section class="how-section" aria-labelledby="howHeading"><div class="section-top"><div><div class="eyebrow">A simple way to reconnect</div><h2 id="howHeading">A few steps. A little peace of mind.</h2></div></div><div class="steps"><article><span class="step-number">01</span><h3>Report</h3><p>Add the details and a few photos. Select the object in each image so the search knows where to look.</p></article><article><span class="step-number">02</span><h3>Discover matches</h3><p>Browse reports and visual suggestions. Look closely at marks and details—similar doesn’t always mean the same.</p></article><article><span class="step-number">03</span><h3>Verify &amp; return</h3><p>Share ownership evidence privately. Arrange a safe handover, then confirm the item is back with its owner.</p></article></div></section><section class="privacy-strip"><strong>Built around trust.</strong><p>Reports and photos are for signed-in members. Ownership evidence stays private to the people reviewing a claim.</p><a href="#privacy">How privacy works →</a></section>`;}
  return {escape,words,states,claimNext,matchStatus,summary,home};
})();
if(typeof module!=='undefined')module.exports=CampusUI;
