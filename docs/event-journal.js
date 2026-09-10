(function(){
  'use strict';
  const KEY='linealert.synthetic.event-journal.v1';
  const MAX=200;
  function load(){try{const raw=localStorage.getItem(KEY);const v=raw?JSON.parse(raw):null;return v&&Array.isArray(v.events)?v:{schemaVersion:1,classification:'synthetic_demo_only',events:[]};}catch(_){return{schemaVersion:1,classification:'synthetic_demo_only',events:[]};}}
  function save(doc){try{doc.events=(doc.events||[]).slice(-MAX);localStorage.setItem(KEY,JSON.stringify(doc));}catch(_){}return doc;}
  function nowSim(){try{return typeof simAbs!=='undefined'&&Number.isFinite(simAbs)?simAbs:null;}catch(_){return null;}}
  function append(input){const t=Number.isFinite(input.time)?input.time:nowSim();if(!Number.isFinite(t))return null;const doc=load();const seq=(doc.events.length?Number(doc.events[doc.events.length-1].seq||0):0)+1;const evt={eventId:'JRN-'+String(seq).padStart(4,'0'),seq,time:t,source:input.source||'linealert/demo-workflow',eventClass:input.eventClass||'WORKFLOW',severity:input.severity||'Information',asset:input.asset||'Labeler 2',message:input.message||'',clockQuality:'synthetic_session_clock',classification:'synthetic_demo_only',fields:input.fields||{}};doc.events.push(evt);save(doc);return evt;}
  function list(){return load().events.slice();}
  function clear(){save({schemaVersion:1,classification:'synthetic_demo_only',events:[]});}
  window.LineAlertEventJournal={KEY,append,list,clear};

  if(typeof document==='undefined'||typeof q!=='function')return;
  function actionTitle(){try{return lastAction&&actions[lastAction]?actions[lastAction].title:(selectedAction&&actions[selectedAction]?actions[selectedAction].title:'bounded action');}catch(_){return'bounded action';}}
  function recordArm(){setTimeout(()=>{try{if(!trialInProgress)return;const title=actionTitle();append({source:'synthetic-operator/labeler2',eventClass:'ACTION',asset:'Labeler 2',message:'Operator recorded one bounded change before verification · '+title,fields:{actionKey:lastAction,incidentId:currentIncident&&currentIncident.id||null,boundary:'one_material_change_from_last_verified_state'}});append({source:'linealert/trial-workflow',eventClass:'TRIAL',asset:'Labeler 2',message:'Five-container trial armed · '+title,fields:{actionKey:lastAction,incidentId:currentIncident&&currentIncident.id||null,equipmentEffect:'none'}});}catch(_){}},0);}

  document.addEventListener('click',function(ev){
    const el=ev.target&&ev.target.closest?ev.target.closest('button'):null;if(!el)return;
    const id=el.id,text=(el.textContent||'').trim();
    if(id==='nextBtn'){
      if(text.includes('Start bounded diagnostic'))setTimeout(()=>{append({source:'synthetic-hmi/packaging-line-1',eventClass:'PRODUCTION',asset:'Packaging Line 1',message:'Operator stopped production for bounded diagnostic response',fields:{incidentId:typeof currentIncident!=='undefined'&&currentIncident?currentIncident.id:null,runMode:'diagnostic'}});},0);
      else if(text.includes('Arm')||text.includes('Restore previous setting'))recordArm();
      else if(text.includes('Resume production'))setTimeout(()=>{append({source:'synthetic-hmi/packaging-line-1',eventClass:'PRODUCTION',asset:'Packaging Line 1',message:'Operator resumed production for recovery verification',fields:{incidentId:typeof currentIncident!=='undefined'&&currentIncident?currentIncident.id:null,runMode:'production_verification'}});},0);
    }
    if(id==='armBtn')recordArm();
    if(id==='hmiBtn')setTimeout(()=>{try{append({source:'synthetic-hmi/labeler2',eventClass:'TRIAL',asset:'Labeler 2',message:'Five-container diagnostic run completed · '+actionTitle(),fields:{actionKey:lastAction,incidentId:currentIncident&&currentIncident.id||null,presentationMs:Number.isFinite(currentVar)?Number(currentVar.toFixed(1)):null}});}catch(_){}},0);
    if(id==='confirmBtn')setTimeout(()=>{try{append({source:'linealert/deterministic',eventClass:'FINDING',severity:'Notice',asset:'Labeler 2',message:'Trial evidence reviewed · '+actionTitle(),fields:{actionKey:lastAction,incidentId:currentIncident&&currentIncident.id||null,trialNumber:Number.isFinite(iteration)?iteration:null,recommendation:recommendation||null}});if(recommendation==='restore_previous')append({source:'linealert/deterministic',eventClass:'RECOMMENDATION',severity:'Notice',asset:'Labeler 2',message:'Restore previous setting recommended before another material change',fields:{incidentId:currentIncident&&currentIncident.id||null,boundary:'recommendation_is_not_equipment_command'}});if(recommendation==='repeat')append({source:'linealert/deterministic',eventClass:'RECOMMENDATION',severity:'Notice',asset:'Labeler 2',message:'No-change repeat recommended before retaining the improvement',fields:{incidentId:currentIncident&&currentIncident.id||null,boundary:'strong_trial_response_is_not_yet_retained_state'}});}catch(_){}},0);
    if(id==='returnProdBtn')setTimeout(()=>{append({source:'synthetic-hmi/packaging-line-1',eventClass:'PRODUCTION',asset:'Packaging Line 1',message:'Operator resumed production for recovery verification',fields:{incidentId:typeof currentIncident!=='undefined'&&currentIncident?currentIncident.id:null,runMode:'production_verification'}});},0);
  });

  try{
    if(typeof completeRecovery==='function'){
      const base=completeRecovery;
      completeRecovery=function(){const id=typeof currentIncident!=='undefined'&&currentIncident?currentIncident.id:null;base();append({source:'linealert/deterministic',eventClass:'RECOVERY',severity:'Notice',asset:'Labeler 2',message:'Production recovery observed; concern closed',fields:{incidentId:id,boundary:'recovery_observed_is_not_root_cause_proof'}});};
    }
  }catch(_){}
})();
