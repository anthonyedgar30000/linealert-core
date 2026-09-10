(function(){
  'use strict';

  const VERIFY_TITLE='Verify guide / spacing against marked reference';
  const INSPECT_TITLE='Inspect guide / spacing against marked reference';
  const RESTORE_TITLE='Restore guide / spacing to approved marked setup reference';
  const RUNNING_GUIDE_ADJUSTMENT_COMMISSIONED=true;

  let installed=false;
  let guideIncidentId=null;
  let guideStage='idle';
  let guideObservation=null;
  let controlPending=false;
  let controlError=null;
  let pendingResumeVerification=null;
  let restoreSourceSequence=null;
  let productionVerificationQueued=false;

  const priorRenderHero=renderHero;

  function el(id){return document.getElementById(id);}

  function sourceStatus(){
    try{
      return window.LineAlertOpcuaSource&&window.LineAlertOpcuaSource.status
        ?window.LineAlertOpcuaSource.status()
        :null;
    }catch(_){return null;}
  }

  function opcActive(){
    const status=sourceStatus();
    return !!(status&&status.everActivated&&status.active&&!status.suspended);
  }

  function sourceRunState(){
    const status=sourceStatus();
    if(!status)return null;
    const code=status.runStateCode;
    return code===0||code===1||code===2?code:null;
  }

  function sourceSequence(){
    const status=sourceStatus();
    const sequence=status&&status.sourceSequence;
    return Number.isFinite(Number(sequence))?Number(sequence):null;
  }

  function guideActionAllowed(runState){
    return runState===0||(runState===1&&RUNNING_GUIDE_ADJUSTMENT_COMMISSIONED);
  }

  function syncIncident(){
    const id=currentIncident&&String(currentIncident.id||'').startsWith('OPC-L2-')
      ?currentIncident.id
      :null;
    if(id!==guideIncidentId){
      guideIncidentId=id;
      guideStage=id?'verify':'idle';
      guideObservation=null;
      controlError=null;
      pendingResumeVerification=null;
      restoreSourceSequence=null;
      productionVerificationQueued=false;
    }
  }

  function queueProductionVerification(){
    if(productionVerificationQueued)return;
    productionVerificationQueued=true;
    window.setTimeout(()=>{
      productionVerificationQueued=false;
      if(!opcActive()||!guideIncidentId||guideStage!=='effect_observed')return;
      guideStage='idle';
      startProductionVerification(false);
      renderHero();
    },0);
  }

  function syncWorkflowToSource(){
    const runState=sourceRunState();
    if(
      guideStage==='awaiting_running_effect'
      &&runState===1
      &&restoreSourceSequence!==null
    ){
      const sequence=sourceSequence();
      if(sequence!==null&&sequence>restoreSourceSequence){
        guideStage='effect_observed';
        restoreSourceSequence=null;
        appendHistory(
          'Fresh production observation after guide / spacing restore',
          'Qualified OPC UA advanced after the recorded restore while Labeler 2 remained in production. Fresh response evidence is now available; intervention followed by improvement is not causal proof.'
        );
        appendJournal(
          'source_evidence',
          'Fresh Labeler 2 production evidence observed after guide restore',
          'A new qualified production observation followed the recorded adjustment. Response evidence does not establish mechanism.',
          'linealert-labeler2-opcua-local'
        );
        queueProductionVerification();
      }
    }
    if(runState===1&&pendingResumeVerification!==null){
      const skippedRecommended=pendingResumeVerification;
      pendingResumeVerification=null;
      guideStage='idle';
      startProductionVerification(skippedRecommended);
    }
    return runState;
  }

  function appendHistory(title,detail){
    const history=el('history');
    if(!history)return;
    const row=document.createElement('div');
    row.innerHTML='<b>'+title+'</b><small>'+detail+'</small>';
    history.appendChild(row);
  }

  function appendJournal(type,title,detail,source){
    if(!window.LineAlertEventJournal)return;
    try{
      window.LineAlertEventJournal.append({
        type,
        asset:'Labeler 2',
        title,
        detail,
        source
      });
    }catch(_){}
  }

  function observedRelation(observation){
    const offset=Number(observation&&observation.observed_offset_mm);
    if(observation&&observation.within_reference){
      return 'guide / spacing matches the marked reference';
    }
    if(Number.isFinite(offset)){
      return 'guide / spacing '+Math.abs(offset).toFixed(1)+' mm outside the marked reference';
    }
    return 'guide / spacing outside the marked reference';
  }

  async function demoControl(action,extra){
    controlPending=true;
    controlError=null;
    renderHero();
    try{
      const response=await fetch('/api/demo-control',{
        method:'POST',
        cache:'no-store',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify(Object.assign({action},extra||{}))
      });
      let payload={};
      try{payload=await response.json();}catch(_){}
      if(!response.ok||payload.accepted===false){
        throw new Error(payload.reason||('simulator control '+response.status));
      }
      return payload;
    }finally{
      controlPending=false;
      renderHero();
    }
  }

  async function inspectGuide(){
    const runState=sourceRunState();
    if(!guideActionAllowed(runState))return;
    try{
      const observation=await demoControl('inspect_guide');
      guideObservation=observation;
      guideStage=observation.within_reference?'within_reference':'restore_available';
      const relation=observedRelation(observation);
      appendHistory(
        'Guide / spacing inspection',
        'Observed: '+relation+'. Human observation is evidence with source identity; it is not OPC UA machine truth or causal proof.'
      );
      appendJournal(
        'human_observation',
        'Guide / spacing reference observation recorded',
        'Observed: '+relation+'. Classification: synthetic human observation.',
        'simulated-operator'
      );
    }catch(err){
      controlError=err&&err.message?err.message:'guide verification failed';
    }
    renderHero();
  }

  async function restoreGuide(){
    const runState=sourceRunState();
    if(!guideActionAllowed(runState)||!guideObservation||guideObservation.within_reference)return;
    try{
      const receipt=await demoControl(
        'restore_guide',
        {observation_id:guideObservation.observation_id}
      );
      lastAction='guide';
      if(runState===1){
        const sequence=Number(receipt&&receipt.sequence_at_action);
        restoreSourceSequence=Number.isFinite(sequence)?sequence:sourceSequence();
        guideStage='awaiting_running_effect';
      }else{
        guideStage='restored';
      }
      appendHistory(
        'Simulator intervention · guide / spacing restored to reference',
        'One bounded guide / spacing adjustment was recorded after an out-of-reference observation. Fresh OPC UA evidence is required before judging the effect.'
      );
      appendJournal(
        'operator_intervention',
        'Guide / spacing restored to approved synthetic reference',
        'Recorded adjustment after the current guide observation. Intervention followed by improvement would not prove mechanism.',
        'linealert-labeler2-simulator-control'
      );
    }catch(err){
      controlError=err&&err.message?err.message:'guide restoration failed';
    }
    renderHero();
  }

  async function runDiagnosticBatch(sourceHandler,event){
    if(sourceRunState()!==0)return;
    if(sourceHandler)sourceHandler.call(el('hmiBtn'),event);
    try{
      await demoControl('run_diagnostic_batch');
      appendJournal(
        'simulator_control',
        'Five-container diagnostic batch requested',
        'The simulator will emit the resulting observations through read-only OPC UA.',
        'linealert-labeler2-simulator-control'
      );
    }catch(err){
      controlError=err&&err.message?err.message:'diagnostic batch failed';
      const hmi=el('hmiBtn');
      if(hmi){
        hmi.disabled=false;
        hmi.textContent='Retry emulator 5-container diagnostic batch';
      }
    }
    renderHero();
  }

  async function resumeProduction(skippedRecommended){
    if(sourceRunState()!==0)return;
    try{
      await demoControl('resume_production');
      pendingResumeVerification=skippedRecommended;
      guideStage='awaiting_production';
      appendJournal(
        'simulator_control',
        'Synthetic production resume requested for verification',
        'Production verification starts only after qualified OPC UA reports production running.',
        'linealert-labeler2-simulator-control'
      );
    }catch(err){
      controlError=err&&err.message?err.message:'resume production failed';
    }
    renderHero();
  }

  function renderGuideHero(){
    syncIncident();
    if(!opcActive()||!guideIncidentId||!incident)return;

    const title=el('bestTitle');
    const why=el('bestWhy');
    const next=el('nextBtn');
    if(!title||!why||!next)return;

    const runState=syncWorkflowToSource();

    if(controlPending){
      next.disabled=true;
      next.textContent='Waiting for simulator control acknowledgment…';
      return;
    }
    if(runState===null){
      title.textContent=VERIFY_TITLE;
      why.textContent='Qualified source run state is unavailable. Workflow action is blocked.';
      next.disabled=true;
      next.textContent='Waiting for qualified OPC UA run state';
      return;
    }
    if(controlError){
      why.textContent='Simulator control did not complete: '+controlError+'.';
    }
    if(guideStage==='awaiting_production'){
      title.textContent='Production resume requested';
      why.textContent='Waiting for qualified OPC UA to report production before verification begins.';
      next.disabled=true;
      next.textContent='Waiting for OPC UA production state';
      return;
    }
    if(trialInProgress){
      next.disabled=true;
      next.textContent='Trial armed · execute the emulator diagnostic batch below';
      return;
    }
    if(nextStage==='production_verification')return;
    if(recommendation!=='guide')return;

    if(runState===2){
      title.textContent=VERIFY_TITLE;
      why.textContent='Qualified OPC UA reports a diagnostic run in progress. Wait for the source to return to ordinary production or stopped state before another guide action.';
      next.disabled=true;
      next.textContent='Diagnostic run active · waiting for source state';
      return;
    }

    if(guideStage==='verify'){
      title.textContent=INSPECT_TITLE;
      why.textContent=runState===1
        ?'Labeler 2 is running. This commissioned demo profile permits the external guide / spacing check while production continues.'
        :'Labeler 2 is stopped. Inspect the visible guide / spacing relationship against the marked reference.';
      next.disabled=!guideActionAllowed(runState);
      next.textContent=INSPECT_TITLE;
      return;
    }

    if(guideStage==='restore_available'&&guideObservation){
      const offset=Math.abs(Number(guideObservation.observed_offset_mm));
      title.textContent='Guide / spacing outside marked reference';
      why.textContent='Observed: guide / spacing '+offset.toFixed(1)+' mm outside the marked reference. Restore to the marked reference is the next commissioned demo action; the observation itself does not establish why the deviation occurred.';
      next.disabled=!guideActionAllowed(runState);
      next.textContent=RESTORE_TITLE;
      return;
    }

    if(guideStage==='awaiting_running_effect'){
      title.textContent='Guide / spacing restored to marked reference';
      why.textContent=runState===1
        ?'The adjustment is recorded while Labeler 2 remains in production. Waiting for a fresh qualified production observation before judging the effect.'
        :'The adjustment is recorded. Waiting for ordinary production to resume before judging the effect.';
      next.disabled=true;
      next.textContent='Waiting for fresh 5-container production evidence';
      return;
    }

    if(guideStage==='effect_observed'){
      title.textContent='Fresh production evidence captured';
      why.textContent='A new qualified production observation followed the guide / spacing restore. Production verification is starting; response to the adjustment is not causal proof.';
      next.disabled=true;
      next.textContent='Starting production verification…';
      return;
    }

    if(guideStage==='restored'){
      title.textContent='Guide / spacing restored to approved reference';
      why.textContent='The adjustment was recorded while Labeler 2 was stopped. Arm a bounded diagnostic run and let fresh OPC UA observations show what changed.';
      next.disabled=false;
      next.textContent='Arm 5-container trial after restore';
      return;
    }

    if(guideStage==='within_reference'){
      title.textContent='Guide / spacing matches marked reference';
      why.textContent='Observed: guide / spacing matches the marked reference. No guide correction is indicated from this observation; choose another commissioned check or escalate.';
      next.disabled=true;
      next.textContent='No guide correction indicated';
    }
  }

  renderHero=function(){
    priorRenderHero();
    renderGuideHero();
  };

  function installOverrides(){
    if(installed||!sourceStatus()||!sourceStatus().everActivated)return;
    const next=el('nextBtn');
    const hmi=el('hmiBtn');
    const returnProd=el('returnProdBtn');
    const confirm=el('confirmBtn');
    if(!next||!hmi||!returnProd||!confirm)return;

    const priorNext=next.onclick;
    const priorHmi=hmi.onclick;
    const priorReturn=returnProd.onclick;
    const priorConfirm=confirm.onclick;

    next.onclick=async function(event){
      if(!opcActive()){
        if(priorNext)return priorNext.call(this,event);
        return;
      }
      syncIncident();
      const runState=syncWorkflowToSource();
      if(runState===null)return;
      if(nextStage==='production_verification'){
        if(runState===0)await resumeProduction(false);
        return;
      }
      if(!incident||recommendation!=='guide'){
        if(priorNext)return priorNext.call(this,event);
        return;
      }
      if(runState===2)return;
      if(guideStage==='verify'&&guideActionAllowed(runState)){
        await inspectGuide();
        return;
      }
      if(guideStage==='restore_available'&&guideActionAllowed(runState)){
        await restoreGuide();
        return;
      }
      if(guideStage==='restored'&&runState===0){
        armTrial('guide');
        renderHero();
      }
    };

    hmi.onclick=async function(event){
      if(!opcActive()||!trialInProgress){
        if(priorHmi)return priorHmi.call(this,event);
        return;
      }
      if(sourceRunState()!==0)return;
      await runDiagnosticBatch(priorHmi,event);
    };

    returnProd.onclick=async function(event){
      if(!opcActive()){
        if(priorReturn)return priorReturn.call(this,event);
        return;
      }
      if(sourceRunState()!==0||trialInProgress||!lastConfirmedTrial)return;
      await resumeProduction(nextStage!=='production_verification');
    };

    confirm.onclick=function(event){
      if(priorConfirm)priorConfirm.call(this,event);
      if(opcActive()&&lastAction==='repeat'&&lastConfirmedTrial){
        recommendation=null;
        nextStage='production_verification';
        selectedAction='repeat';
        renderActions();
      }
    };

    installed=true;
    renderHero();
  }

  window.setInterval(installOverrides,200);
})();
