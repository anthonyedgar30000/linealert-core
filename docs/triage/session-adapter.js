(function(){
  'use strict';
  const store=window.LineAlertDemoSession;
  if(!store)return;
  const MAX_AWAY_SECONDS=15*60;

  function text(id){const el=document.getElementById(id);return el?el.textContent:''}
  function visible(id){const el=document.getElementById(id);return !!el&&!el.classList.contains('hidden')}
  function incidentCopy(e){
    if(!e)return null;
    return {
      id:e.id,kind:e.kind,time:e.time,title:e.title,summary:e.summary,initialVar:e.initialVar,
      quality:e.quality,camera:e.camera,recommendation:e.recommendation,rationale:e.rationale,status:e.status,
      shift:e.shift?{code:e.shift.code,name:e.shift.name,start:e.shift.start,end:e.shift.end,hard:e.shift.hard,shiftDate:e.shift.shiftDate}:null
    };
  }
  function currentStateName(){
    if(recoveryObserved)return 'RECOVERED';
    if(productionVerification)return 'VERIFY';
    if(mode==='diagnostic')return 'DIAGNOSTIC';
    if(incident)return 'WATCH';
    return 'NORMAL';
  }
  function latestTrial(){
    if(!lastConfirmedTrial||!lastAction||!actions[lastAction])return null;
    const out=actions[lastAction].out;
    return {
      iteration,
      actionKey:lastAction,
      actionTitle:actions[lastAction].title,
      beforeVar:trialBeforeVar,
      afterVar:out.v,
      accepted:out.accepted,
      aligned:out.aligned,
      skew:out.skew,
      interpretation:out.text
    };
  }
  function snapshot(){
    const shift=shiftAt(simAbs);
    const rec=recommendation&&actions[recommendation]?actions[recommendation]:null;
    return {
      source:'plant_canvas',
      simAbs,
      simDate:dateKey(simAbs),
      simTime:fmt(simAbs,true),
      shift:{code:shift.code,name:shift.name,shiftDate:shift.shiftDate},
      posture:text('postureTop'),
      runMode:text('modeTop'),
      state:currentStateName(),
      mode,
      incident,
      recoveryObserved,
      productionVerification,
      currentIncident:incidentCopy(currentIncident),
      asset:currentIncident?'Labeler 2':null,
      recommendation,
      recommendationTitle:rec?rec.title:null,
      recommendationWhy:rec?rec.why:null,
      selectedAction,
      lastAction,
      iteration,
      nextStage,
      trialBeforeVar,
      trialInProgress,
      lastConfirmedTrial,
      latestTrial:latestTrial(),
      discipline:window.LineAlertTrialDiscipline?window.LineAlertTrialDiscipline.snapshot():null,
      verification:{
        streak:verificationStreak,
        target:VERIFY_TARGET,
        resets:verificationResets,
        accumulator:verificationAccumulator,
        baseVar:verificationBaseVar,
        cameraHealthy:verificationCameraHealthy,
        qualityHealthy:verificationQualityHealthy
      },
      evidence:{
        presentation:text('varVal'),
        quality:text('qualityVal'),
        throughput:text('throughputVal'),
        camera:text('cameraVal')
      },
      timing:{
        nextWindow:text('nextWindow'),
        runway:text('runway'),
        maintenanceEta:text('maintEta'),
        slack:text('slack')
      },
      counters:{processed,fillerCount,palletCount,buffer,liveTick,currentVar},
      selected,
      handledIncidentIds:Array.from(handledIncidentIds),
      fast:{active:fast,target:fastTarget,event:incidentCopy(fastEvent)},
      decisionHistoryHtml:text('history')?document.getElementById('history').innerHTML:'',
      trialDom:{
        visible:visible('trialSection'),
        state:text('trialState'),
        action:text('trialAction'),
        resultVisible:visible('trialResult'),
        resultHtml:document.getElementById('trialResult')?document.getElementById('trialResult').innerHTML:'',
        confirmVisible:visible('confirmBtn'),
        hmiDisabled:document.getElementById('hmiBtn')?document.getElementById('hmiBtn').disabled:false,
        hmiText:text('hmiBtn')
      }
    };
  }
  function publish(){
    try{return store.save(snapshot())}catch(err){console.warn('LineAlert demo session publish skipped',err);return null}
  }
  function restoreEvidence(saved){
    if(!saved.evidence)return;
    const map={varVal:'presentation',qualityVal:'quality',throughputVal:'throughput',cameraVal:'camera'};
    Object.entries(map).forEach(([id,key])=>{const el=document.getElementById(id);if(el&&saved.evidence[key])el.textContent=saved.evidence[key]});
    const nodeVar=document.getElementById('nodeVar');
    if(nodeVar&&saved.counters&&Number.isFinite(saved.counters.currentVar))nodeVar.textContent=saved.counters.currentVar.toFixed(1)+' ms';
  }
  function restore(saved){
    if(!saved||saved.source!=='plant_canvas'||!Number.isFinite(saved.simAbs))return false;
    try{
      const away=Math.max(0,Math.min(MAX_AWAY_SECONDS,Math.floor((Date.now()-(saved.updatedAtMs||Date.now()))/1000)));
      simAbs=saved.simAbs+away;
      mode=saved.mode||'production';
      incident=!!saved.incident;
      recoveryObserved=!!saved.recoveryObserved;
      productionVerification=!!saved.productionVerification;
      currentIncident=saved.currentIncident||null;
      recommendation=saved.recommendation||null;
      selectedAction=saved.selectedAction||recommendation||'guide';
      lastAction=saved.lastAction||null;
      iteration=Number.isFinite(saved.iteration)?saved.iteration:0;
      nextStage=saved.nextStage||'action';
      trialBeforeVar=Number.isFinite(saved.trialBeforeVar)?saved.trialBeforeVar:null;
      trialInProgress=!!saved.trialInProgress;
      lastConfirmedTrial=!!saved.lastConfirmedTrial;
      selected=saved.selected||((currentIncident||recoveryObserved||productionVerification)?'labeler':'filler');
      if(saved.counters){
        processed=Number.isFinite(saved.counters.processed)?saved.counters.processed:processed;
        fillerCount=Number.isFinite(saved.counters.fillerCount)?saved.counters.fillerCount:fillerCount;
        palletCount=Number.isFinite(saved.counters.palletCount)?saved.counters.palletCount:palletCount;
        buffer=Number.isFinite(saved.counters.buffer)?saved.counters.buffer:buffer;
        liveTick=Number.isFinite(saved.counters.liveTick)?saved.counters.liveTick:liveTick;
        currentVar=Number.isFinite(saved.counters.currentVar)?saved.counters.currentVar:currentVar;
      }
      if(saved.verification){
        verificationStreak=Number.isFinite(saved.verification.streak)?saved.verification.streak:0;
        verificationResets=Number.isFinite(saved.verification.resets)?saved.verification.resets:0;
        verificationAccumulator=Number.isFinite(saved.verification.accumulator)?saved.verification.accumulator:0;
        verificationBaseVar=Number.isFinite(saved.verification.baseVar)?saved.verification.baseVar:verificationBaseVar;
        verificationCameraHealthy=saved.verification.cameraHealthy!==false;
        verificationQualityHealthy=saved.verification.qualityHealthy!==false;
      }
      handledIncidentIds.clear();
      (saved.handledIncidentIds||[]).forEach(id=>handledIncidentIds.add(id));
      fast=!!(saved.fast&&saved.fast.active);
      fastTarget=saved.fast&&Number.isFinite(saved.fast.target)?saved.fast.target:null;
      fastEvent=saved.fast?saved.fast.event:null;

      if(window.LineAlertTrialDiscipline&&saved.discipline)window.LineAlertTrialDiscipline.restore(saved.discipline);

      const history=document.getElementById('history');
      if(history&&saved.decisionHistoryHtml)history.innerHTML=saved.decisionHistoryHtml;
      if(currentIncident){
        document.getElementById('assetHeadline').textContent=currentIncident.title;
        document.getElementById('assetSummary').textContent=currentIncident.summary;
        document.getElementById('historyRationale').textContent=currentIncident.rationale;
      }
      if(saved.latestTrial&&saved.latestTrial.actionKey&&actions[saved.latestTrial.actionKey]){
        const oldIteration=iteration;
        iteration=saved.latestTrial.iteration||iteration;
        showLastTrial(saved.latestTrial.actionKey,Number.isFinite(saved.latestTrial.beforeVar)?saved.latestTrial.beforeVar:currentVar,actions[saved.latestTrial.actionKey].out);
        iteration=oldIteration;
      }else show('lastTrialCard',false);

      if(saved.trialDom&&saved.trialDom.visible){
        show('trialSection');
        document.getElementById('trialState').textContent=saved.trialDom.state||'TRIAL ARMED · WAITING FOR HMI';
        document.getElementById('trialAction').textContent=saved.trialDom.action||'';
        document.getElementById('trialResult').innerHTML=saved.trialDom.resultHtml||'';
        show('trialResult',!!saved.trialDom.resultVisible);
        show('confirmBtn',!!saved.trialDom.confirmVisible);
        document.getElementById('hmiBtn').disabled=!!saved.trialDom.hmiDisabled;
        if(saved.trialDom.hmiText)document.getElementById('hmiBtn').textContent=saved.trialDom.hmiText;
      }else show('trialSection',false);

      document.getElementById('concernCount').textContent=incident||productionVerification?'1':'0';
      document.getElementById('watchPill').textContent=incident||productionVerification?'Watch':'Normal';
      document.getElementById('labelerNode').classList.toggle('watch',incident||productionVerification);
      renderActions();
      renderVerification();
      selectAsset(selected);
      maybeTriggerIncident();
      clock();
      if(away>0)live(away); else restoreEvidence(saved);
      renderTicketHistory();
      renderOps();
      updateSpeedControl();
      return true;
    }catch(err){
      console.warn('LineAlert demo session restore skipped',err);
      return false;
    }
  }

  const saved=store.load();
  if(!restore(saved))publish(); else publish();
  window.addEventListener('beforeunload',publish);
  document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='hidden')publish()});
  setInterval(publish,500);
})();
