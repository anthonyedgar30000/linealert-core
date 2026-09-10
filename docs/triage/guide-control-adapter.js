(function(){
  'use strict';

  const VERIFY_TITLE='Verify guide / spacing against approved setup reference';
  const RESTORE_TITLE='Restore guide / spacing to approved marked setup reference';

  let installed=false;
  let guideIncidentId=null;
  let guideStage='idle';
  let guideObservation=null;
  let controlPending=false;
  let controlError=null;
  let pendingResumeVerification=null;

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
    }
  }

  function syncWorkflowToSource(){
    const runState=sourceRunState();
    if(runState===0&&guideStage==='awaiting_stop'){
      if(mode!=='diagnostic')enterDiagnostic();
      guideStage='verify';
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

  async function stopForDiagnostic(){
    if(sourceRunState()!==1)return;
    try{
      await demoControl('stop_for_diagnostic');
      guideStage='awaiting_stop';
      appendJournal(
        'simulator_control',
        'Synthetic Labeler stop requested for bounded diagnostic',
        'Control was acknowledged; inspection stays blocked until qualified OPC UA reports stopped.',
        'linealert-labeler2-simulator-control'
      );
    }catch(err){
      controlError=err&&err.message?err.message:'simulator control failed';
    }
    renderHero();
  }

  async function inspectGuide(){
    if(sourceRunState()!==0)return;
    try{
      const observation=await demoControl('inspect_guide');
      guideObservation=observation;
      guideStage=observation.within_reference?'within_reference':'restore_available';
      const offset=Number(observation.observed_offset_mm);
      const offsetText=Number.isFinite(offset)?Math.abs(offset).toFixed(1)+' mm':'an observed amount';
      const relation=observation.within_reference
        ?'matches the approved synthetic reference'
        :'is '+offsetText+' outside the approved synthetic reference';
      appendHistory(
        'Simulated operator observation · guide / spacing checked',
        relation+'. Human observation is evidence with source identity; it is not OPC UA machine truth or causal proof.'
      );
      appendJournal(
        'human_observation',
        'Guide / spacing reference observation recorded',
        relation+'. Classification: synthetic human observation.',
        'simulated-operator'
      );
    }catch(err){
      controlError=err&&err.message?err.message:'guide verification failed';
    }
    renderHero();
  }

  async function restoreGuide(){
    if(sourceRunState()!==0||!guideObservation||guideObservation.within_reference)return;
    try{
      await demoControl('restore_guide',{observation_id:guideObservation.observation_id});
      guideStage='restored';
      appendHistory(
        'Simulator intervention · guide / spacing restored to reference',
        'The synthetic operator applied one bounded change after an out-of-reference observation. Fresh OPC UA evidence is required before another material change.'
      );
      appendJournal(
        'operator_intervention',
        'Guide / spacing restored to approved synthetic reference',
        'Simulator-only intervention after recorded observation. Intervention followed by improvement would not prove mechanism.',
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
      why.textContent='Simulator-only control did not complete: '+controlError+'. No equipment action was taken.';
    }
    if(guideStage==='awaiting_stop'){
      title.textContent=VERIFY_TITLE;
      why.textContent='Stop request acknowledged. Inspection remains blocked until qualified OPC UA reports run_state_code 0.';
      next.disabled=true;
      next.textContent='Waiting for OPC UA stopped state';
      return;
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

    title.textContent=VERIFY_TITLE;

    if(runState===1){
      why.textContent='Inspection first. Qualified OPC UA still reports production running, so the simulated guide observation is blocked until the source reports stopped.';
      next.disabled=false;
      next.textContent='Stop synthetic machine for bounded diagnostic';
      return;
    }

    if(runState===2){
      why.textContent='Qualified OPC UA reports a diagnostic run in progress. Wait for the source to return to the stopped diagnostic state before another workflow action.';
      next.disabled=true;
      next.textContent='Diagnostic run active · waiting for source state';
      return;
    }

    if(guideStage==='verify'){
      why.textContent='Qualified OPC UA reports the synthetic Labeler stopped. Compare the visible guide / spacing relationship with the approved synthetic reference before considering any material change.';
      next.disabled=false;
      next.textContent='Record simulated guide / spacing observation';
      return;
    }

    if(guideStage==='restore_available'&&guideObservation){
      const offset=Math.abs(Number(guideObservation.observed_offset_mm));
      title.textContent='Guide / spacing appears outside approved reference';
      why.textContent='Simulated operator observation: '+offset.toFixed(1)+' mm outside reference. In this demo the operator is commissioned to restore this bounded setup reference. Observation ≠ diagnosis; recommendation ≠ universal authority.';
      next.disabled=false;
      next.textContent=RESTORE_TITLE;
      return;
    }

    if(guideStage==='restored'){
      title.textContent='Guide / spacing restored to approved reference';
      why.textContent='One simulator-only material change is recorded. Do not infer success yet; arm a bounded run and let fresh OPC UA observations show what changed.';
      next.disabled=false;
      next.textContent='Arm 5-container trial after restore';
      return;
    }

    if(guideStage==='within_reference'){
      title.textContent='Guide / spacing matches approved reference';
      why.textContent='No guide correction is indicated from this observation. Matching the reference does not prove the guide path healthy; record the result and choose another commissioned check or escalate.';
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
      if(runState===1){
        await stopForDiagnostic();
        return;
      }
      if(runState!==0)return;
      if(guideStage==='verify'){
        await inspectGuide();
        return;
      }
      if(guideStage==='restore_available'){
        await restoreGuide();
        return;
      }
      if(guideStage==='restored'){
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
