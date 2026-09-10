(function(){
  'use strict';

  const CONTEXT_ID='labelerGuideWorkflowContext';

  function el(id){return document.getElementById(id);}

  function activeGuideIncident(){
    try{
      return incident===true
        &&currentIncident
        &&String(currentIncident.id||'').startsWith('OPC-L2-');
    }catch(_){return false;}
  }

  function ensureContext(){
    let box=el(CONTEXT_ID);
    if(box)return box;
    const state=el('nodeState');
    if(!state)return null;
    box=document.createElement('div');
    box.id=CONTEXT_ID;
    box.hidden=true;
    box.style.cssText='margin-top:8px;padding-top:7px;border-top:1px solid #e1e5e2;display:grid;gap:4px';
    state.insertAdjacentElement('afterend',box);
    return box;
  }

  function latestWorkflowFacts(){
    const history=el('history');
    if(!history)return{observation:null,restored:false};
    let observation=null;
    let restored=false;
    Array.from(history.children).forEach(row=>{
      const title=row.querySelector('b');
      const detail=row.querySelector('small');
      const titleText=title?(title.textContent||'').trim():'';
      const detailText=detail?(detail.textContent||'').trim():'';
      if(titleText==='Guide / spacing inspection'){
        const match=detailText.match(/^Observed:\s*(.+?)\.\s*(?:Human observation|$)/);
        if(match)observation=match[1];
      }
      if(titleText.startsWith('Simulator intervention · guide / spacing restored to reference')){
        restored=true;
      }
    });
    return{observation,restored};
  }

  function sourceRunState(){
    try{
      const status=window.LineAlertOpcuaSource&&window.LineAlertOpcuaSource.status
        ?window.LineAlertOpcuaSource.status()
        :null;
      return status?Number(status.runStateCode):null;
    }catch(_){return null;}
  }

  function effectState(){
    try{
      if(productionVerification)return'Production verification active';
      if(trialInProgress)return'5-container trial active';
      if(lastConfirmedTrial)return'Bounded trial captured';
    }catch(_){}
    if(sourceRunState()===1)return'Awaiting fresh 5-container production observation';
    return'Awaiting 5-container trial';
  }

  function appendFact(box,label,value){
    const row=document.createElement('div');
    row.style.cssText='display:grid;gap:1px';
    const tag=document.createElement('span');
    tag.textContent=label;
    tag.style.cssText='font-size:.54rem;font-weight:900;letter-spacing:.08em;color:#748078';
    const text=document.createElement('b');
    text.textContent=value;
    text.style.cssText='font-size:.66rem;line-height:1.25;margin:0';
    row.append(tag,text);
    box.appendChild(row);
  }

  function render(){
    const box=ensureContext();
    if(!box)return;
    if(!activeGuideIncident()){
      box.hidden=true;
      box.replaceChildren();
      return;
    }
    const facts=latestWorkflowFacts();
    if(!facts.observation){
      box.hidden=true;
      box.replaceChildren();
      return;
    }
    box.replaceChildren();
    appendFact(box,'OBSERVED',facts.observation);
    if(facts.restored){
      appendFact(box,'ACTION','Guide / spacing restored to marked reference');
      appendFact(box,'VERIFY EFFECT',effectState());
    }
    box.hidden=false;
  }

  render();
  window.setInterval(render,200);
})();
