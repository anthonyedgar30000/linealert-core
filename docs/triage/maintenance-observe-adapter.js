(function(){
  'use strict';

  if(
    typeof opsSnapshot!=='function'||
    typeof maybeTriggerIncident!=='function'||
    typeof schedule!=='function'||
    typeof updateModeLabels!=='function'||
    typeof renderHero!=='function'||
    typeof renderOps!=='function'||
    typeof updateSpeedControl!=='function'||
    typeof live!=='function'
  )return;

  const TARGET_ASSET='Labeler 2';

  function activeMaintenance(abs){
    const snap=opsSnapshot(abs);
    const work=snap.active.find(job=>job.asset===TARGET_ASSET);
    if(!work)return null;
    return {
      active:true,
      asset:TARGET_ASSET,
      workOrderId:work.id,
      title:work.title,
      source:'synthetic_cmms_active_work',
      interpretation:'maintenance_observe'
    };
  }

  function maintenanceActive(){
    return activeMaintenance(simAbs);
  }

  const baseMaybeTriggerIncident=maybeTriggerIncident;
  maybeTriggerIncident=function(){
    // An active maintenance record changes the expected operating context.
    // Do not evaluate normal production concern thresholds against that context.
    if(maintenanceActive())return;
    return baseMaybeTriggerIncident();
  };

  const baseLive=live;
  live=function(delta=1){
    const work=maintenanceActive();
    if(!work)return baseLive(delta);

    // Keep the synthetic telemetry/counters moving so maintenance evidence is not
    // silently discarded, but do not let maintenance-period samples advance a
    // production recovery-verification streak.
    const wasProductionVerification=productionVerification;
    productionVerification=false;
    try{
      return baseLive(delta);
    }finally{
      productionVerification=wasProductionVerification;
    }
  };

  if(typeof enterDiagnostic==='function'){
    const baseEnterDiagnostic=enterDiagnostic;
    enterDiagnostic=function(){
      if(maintenanceActive())return;
      return baseEnterDiagnostic();
    };
  }

  if(typeof armTrial==='function'){
    const baseArmTrial=armTrial;
    armTrial=function(k){
      if(maintenanceActive())return;
      return baseArmTrial(k);
    };
  }

  const baseSchedule=schedule;
  schedule=function(){
    baseSchedule();
    const work=maintenanceActive();
    if(!work)return;

    q('runwayLabel').textContent='LINEALERT MODE';
    q('runway').textContent='Observe only';
    q('maintLabel').textContent='ACTIVE MAINTENANCE';
    q('maintEta').textContent=work.workOrderId;
    q('slackLabel').textContent='PRODUCTION FINDINGS';
    q('slack').textContent='Paused';
    q('assetSlackLabel').textContent='FINDINGS';
    q('assetSlack').textContent='Paused';
    q('assetEtaLabel').textContent='WORK ORDER';
    q('assetEta').textContent=work.workOrderId;
    q('postureTop').textContent='MAINTENANCE · NORMAL INTERPRETATION PAUSED';
  };

  const baseUpdateModeLabels=updateModeLabels;
  updateModeLabels=function(){
    baseUpdateModeLabels();
    const work=maintenanceActive();
    if(!work)return;

    q('nodeState').textContent='Maintenance · observe only';
    q('assetState').textContent='MAINTENANCE';
    q('modeTop').textContent='MAINTENANCE · OBSERVE ONLY';
  };

  const baseRenderHero=renderHero;
  renderHero=function(){
    baseRenderHero();
    const work=maintenanceActive();
    if(!work)return;

    q('bestTitle').textContent='Maintenance in progress · normal recommendations paused';
    q('bestWhy').textContent=work.workOrderId+' · '+work.title+'. Telemetry and event capture continue, but normal production findings, troubleshooting recommendations and recovery verification are suspended for Labeler 2 while this maintenance record is active. Maintenance activity is context, not proof of machine condition.';
    q('nextBtn').textContent='Maintenance observe · no LineAlert action';
    q('nextBtn').disabled=true;
    show('returnProdBtn',false);
    show('selectionBox',false);
    show('trialSection',false);
  };

  const baseRenderOps=renderOps;
  renderOps=function(){
    baseRenderOps();
    const work=maintenanceActive();
    if(!work)return;
    q('etaExplain').textContent=work.workOrderId+' is active on Labeler 2. LineAlert remains connected for telemetry/event capture while normal production interpretation is suspended for the maintained asset.';
  };

  const baseUpdateSpeedControl=updateSpeedControl;
  updateSpeedControl=function(){
    const work=maintenanceActive();
    if(!work)return baseUpdateSpeedControl();
    q('speedBtn').disabled=true;
    q('speedBtn').textContent='● 1× MAINTENANCE OBSERVE';
    q('speedNote').textContent='Active maintenance on Labeler 2 · incident fast-forward and normal production interpretation are paused.';
  };

  window.LineAlertMaintenanceObserve={
    snapshot:()=>{
      const work=maintenanceActive();
      return work||{
        active:false,
        asset:TARGET_ASSET,
        source:'synthetic_cmms_active_work',
        interpretation:'normal_monitoring'
      };
    }
  };

  schedule();
  updateModeLabels();
  renderHero();
  renderOps();
  updateSpeedControl();
})();
