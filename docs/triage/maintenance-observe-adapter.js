(function(){
  'use strict';

  if(
    typeof shiftJobs!=='function'||
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
  const STATE_KEY='linealert.synthetic.maintenance-lifecycle.v1';
  const POST_MAINT_TARGET=10;
  const POST_MAINT_VAR_MAX=11.5;
  const PLANNED_PM_START=18*H+20*60;
  const PLANNED_PM_DURATION=30*60;
  const pendingEvents=[];

  function blankState(){
    return {
      schemaVersion:1,
      activeWorkOrderId:null,
      lastWork:null,
      postMaintenanceObservation:false,
      postCount:0,
      postResets:0,
      justExitedMaintenance:false,
      completedWorkOrderId:null
    };
  }

  function loadState(){
    try{
      const raw=localStorage.getItem(STATE_KEY);
      const parsed=raw?JSON.parse(raw):null;
      return parsed&&parsed.schemaVersion===1?Object.assign(blankState(),parsed):blankState();
    }catch(_){
      return blankState();
    }
  }

  function saveState(){
    try{localStorage.setItem(STATE_KEY,JSON.stringify(state));}catch(_){}
  }

  let state=loadState();

  // Give the synthetic demo a real, deterministic way to encounter the maintenance
  // lifecycle without rewriting the preserved PR #102 baseline. The existing evening
  // maintenance window receives one Labeler 2 inspection on clean synthetic shifts.
  // This is demo scheduling, not an OEM maintenance recommendation.
  const baseShiftJobs=shiftJobs;
  shiftJobs=function(shift){
    const jobs=baseShiftJobs(shift);
    if(shift.code!=='E'||shiftEvent(shift))return jobs;
    if(jobs.some(job=>job.asset===TARGET_ASSET))return jobs;
    const arrival=dayStart(shift.start)+PLANNED_PM_START;
    const planned={
      id:'WO-SYN-'+shift.shiftDate.replaceAll('-','')+'-E-L2-PM',
      type:'Inspection',
      line:'Packaging Line 1',
      asset:TARGET_ASSET,
      title:'Scheduled Labeler 2 inspection / cleaning',
      priority:'P3',
      skill:'mechanical',
      arrival,
      duration:PLANNED_PM_DURATION,
      syntheticMaintenance:true
    };
    return jobs.concat(planned).sort((a,b)=>a.arrival-b.arrival);
  };

  function activeMaintenance(abs){
    const snap=opsSnapshot(abs);
    const work=snap.active.find(job=>job.asset===TARGET_ASSET);
    if(!work)return null;
    return {
      active:true,
      asset:TARGET_ASSET,
      workOrderId:work.id,
      title:work.title,
      start:work.start,
      end:work.end,
      source:'synthetic_cmms_active_work',
      interpretation:'maintenance_observe'
    };
  }

  function eventAlreadyRecorded(lifecycleKey){
    try{
      if(!window.LineAlertEventJournal)return false;
      return window.LineAlertEventJournal.list().some(evt=>evt.fields&&evt.fields.lifecycleKey===lifecycleKey);
    }catch(_){
      return false;
    }
  }

  function queueEvent(input){
    pendingEvents.push(input);
  }

  function flushEvents(){
    if(!window.LineAlertEventJournal)return;
    while(pendingEvents.length){
      const input=pendingEvents.shift();
      const lifecycleKey=input.fields&&input.fields.lifecycleKey;
      if(lifecycleKey&&eventAlreadyRecorded(lifecycleKey))continue;
      window.LineAlertEventJournal.append(input);
    }
  }

  function syncLifecycle(){
    flushEvents();
    const work=activeMaintenance(simAbs);

    if(work&&state.activeWorkOrderId!==work.workOrderId){
      state.activeWorkOrderId=work.workOrderId;
      state.lastWork=work;
      state.postMaintenanceObservation=false;
      state.postCount=0;
      state.postResets=0;
      state.justExitedMaintenance=false;
      queueEvent({
        source:'synthetic-cmms/packaging-line-1',
        eventClass:'MAINTENANCE',
        asset:TARGET_ASSET,
        message:'Maintenance work started · '+work.workOrderId+' · '+work.title,
        fields:{
          workOrderId:work.workOrderId,
          lifecycleKey:work.workOrderId+'|start',
          boundary:'maintenance_context_suspends_normal_production_interpretation'
        }
      });
      saveState();
    }

    if(!work&&state.activeWorkOrderId){
      const ended=state.lastWork;
      state.activeWorkOrderId=null;
      state.postMaintenanceObservation=true;
      state.postCount=0;
      state.postResets=0;
      state.justExitedMaintenance=true;
      if(ended){
        queueEvent({
          source:'synthetic-cmms/packaging-line-1',
          eventClass:'MAINTENANCE',
          asset:TARGET_ASSET,
          message:'Maintenance work completed · '+ended.workOrderId,
          fields:{
            workOrderId:ended.workOrderId,
            lifecycleKey:ended.workOrderId+'|complete',
            boundary:'maintenance_completion_is_not_proof_of_health'
          }
        });
        queueEvent({
          source:'linealert/deterministic',
          eventClass:'OBSERVATION',
          asset:TARGET_ASSET,
          message:'Post-maintenance observation started; normal production interpretation remains paused',
          fields:{
            workOrderId:ended.workOrderId,
            lifecycleKey:ended.workOrderId+'|post-observe-start',
            targetContainers:POST_MAINT_TARGET,
            boundary:'observation_is_not_return_to_service_authorization'
          }
        });
      }
      saveState();
    }

    flushEvents();
    return work;
  }

  function maintenanceSnapshot(){
    const work=syncLifecycle();
    if(work)return work;
    if(state.postMaintenanceObservation){
      return {
        active:false,
        postMaintenanceObservation:true,
        asset:TARGET_ASSET,
        workOrderId:state.lastWork&&state.lastWork.workOrderId||null,
        title:state.lastWork&&state.lastWork.title||null,
        observedContainers:state.postCount,
        targetContainers:POST_MAINT_TARGET,
        resets:state.postResets,
        source:'synthetic_post_maintenance_observation',
        interpretation:'post_maintenance_observe'
      };
    }
    return {
      active:false,
      postMaintenanceObservation:false,
      asset:TARGET_ASSET,
      source:'synthetic_cmms_active_work',
      interpretation:'normal_monitoring'
    };
  }

  function completePostMaintenanceObservation(){
    const work=state.lastWork;
    state.postMaintenanceObservation=false;
    state.completedWorkOrderId=work&&work.workOrderId||null;
    state.justExitedMaintenance=false;
    if(work){
      queueEvent({
        source:'linealert/deterministic',
        eventClass:'OBSERVATION',
        severity:'Notice',
        asset:TARGET_ASSET,
        message:'Post-maintenance observation complete; normal production interpretation resumed',
        fields:{
          workOrderId:work.workOrderId,
          lifecycleKey:work.workOrderId+'|post-observe-complete',
          observedContainers:POST_MAINT_TARGET,
          boundary:'normal_interpretation_resumed_not_maintenance_success_or_safety_approval'
        }
      });
    }
    saveState();
    flushEvents();
  }

  const baseMaybeTriggerIncident=maybeTriggerIncident;
  maybeTriggerIncident=function(){
    const snapshot=maintenanceSnapshot();
    if(snapshot.active||snapshot.postMaintenanceObservation)return;
    return baseMaybeTriggerIncident();
  };

  const baseLive=live;
  live=function(delta=1){
    const snapshot=maintenanceSnapshot();

    if(snapshot.active){
      // Advance the synthetic clock-facing sensor loop under a non-production mode so
      // product counters and production-rate evidence do not keep accumulating while
      // Labeler 2 is under maintenance. Connectivity/history remain available, but the
      // production interpretation layer is deliberately quiet.
      const previousMode=mode;
      const previousVerification=productionVerification;
      mode='maintenance';
      productionVerification=false;
      try{
        baseLive(delta);
      }finally{
        mode=previousMode;
        productionVerification=previousVerification;
      }
      q('nodeVar').textContent='Not scored · maintenance';
      q('varVal').textContent='Not evaluated · maintenance';
      q('throughputVal').textContent='0.0/min';
      q('cameraVal').textContent='Maintenance context · not scored';
      q('qualityVal').textContent='Not evaluated';
      return;
    }

    if(snapshot.postMaintenanceObservation){
      const before=processed;
      const effectiveDelta=state.justExitedMaintenance?1:delta;
      state.justExitedMaintenance=false;
      const result=baseLive(effectiveDelta);
      const planned=plannedWindow(simAbs);

      if(mode==='production'&&planned.running&&!incident&&!productionVerification){
        const gained=Math.max(0,processed-before);
        if(gained>0){
          if(currentVar<=POST_MAINT_VAR_MAX){
            state.postCount=Math.min(POST_MAINT_TARGET,state.postCount+gained);
          }else{
            state.postCount=0;
            state.postResets++;
          }
          saveState();
        }
        if(state.postCount>=POST_MAINT_TARGET){
          completePostMaintenanceObservation();
        }
      }
      renderHero();
      updateSpeedControl();
      return result;
    }

    return baseLive(delta);
  };

  if(typeof enterDiagnostic==='function'){
    const baseEnterDiagnostic=enterDiagnostic;
    enterDiagnostic=function(){
      const snapshot=maintenanceSnapshot();
      if(snapshot.active||snapshot.postMaintenanceObservation)return;
      return baseEnterDiagnostic();
    };
  }

  if(typeof armTrial==='function'){
    const baseArmTrial=armTrial;
    armTrial=function(k){
      const snapshot=maintenanceSnapshot();
      if(snapshot.active||snapshot.postMaintenanceObservation)return;
      return baseArmTrial(k);
    };
  }

  const baseSchedule=schedule;
  schedule=function(){
    baseSchedule();
    const snapshot=maintenanceSnapshot();
    if(snapshot.active){
      q('runwayLabel').textContent='LINEALERT MODE';
      q('runway').textContent='Observe only';
      q('maintLabel').textContent='ACTIVE MAINTENANCE';
      q('maintEta').textContent=snapshot.workOrderId;
      q('slackLabel').textContent='PRODUCTION FINDINGS';
      q('slack').textContent='Paused';
      q('assetSlackLabel').textContent='FINDINGS';
      q('assetSlack').textContent='Paused';
      q('assetEtaLabel').textContent='WORK ORDER';
      q('assetEta').textContent=snapshot.workOrderId;
      q('postureTop').textContent='MAINTENANCE · NORMAL INTERPRETATION PAUSED';
      return;
    }
    if(snapshot.postMaintenanceObservation){
      q('runwayLabel').textContent='LINEALERT MODE';
      q('runway').textContent='Post-maintenance';
      q('maintLabel').textContent='LAST WORK ORDER';
      q('maintEta').textContent=snapshot.workOrderId||'Recorded';
      q('slackLabel').textContent='OBSERVATION';
      q('slack').textContent=snapshot.observedContainers+' / '+snapshot.targetContainers;
      q('assetSlackLabel').textContent='OBSERVATION';
      q('assetSlack').textContent=snapshot.observedContainers+' / '+snapshot.targetContainers;
      q('assetEtaLabel').textContent='WORK ORDER';
      q('assetEta').textContent=snapshot.workOrderId||'Recorded';
      q('postureTop').textContent='POST-MAINTENANCE · INTERPRETATION PAUSED';
    }
  };

  const baseUpdateModeLabels=updateModeLabels;
  updateModeLabels=function(){
    baseUpdateModeLabels();
    const snapshot=maintenanceSnapshot();
    if(snapshot.active){
      q('nodeState').textContent='Maintenance · observe only';
      q('assetState').textContent='MAINTENANCE';
      q('modeTop').textContent='MAINTENANCE · OBSERVE ONLY';
      return;
    }
    if(snapshot.postMaintenanceObservation){
      q('nodeState').textContent='Production · post-maintenance observe';
      q('assetState').textContent='OBSERVE';
      q('modeTop').textContent='POST-MAINTENANCE OBSERVATION';
    }
  };

  const baseRenderHero=renderHero;
  renderHero=function(){
    baseRenderHero();
    const snapshot=maintenanceSnapshot();
    if(snapshot.active){
      q('bestTitle').textContent='Maintenance in progress · normal recommendations paused';
      q('bestWhy').textContent=snapshot.workOrderId+' · '+snapshot.title+'. Source connectivity and event chronology remain available, but normal production findings, troubleshooting recommendations and recovery verification are suspended for Labeler 2 while this maintenance record is active. Maintenance activity is context, not proof of machine condition.';
      q('nextBtn').textContent='Maintenance observe · no LineAlert action';
      q('nextBtn').disabled=true;
      show('returnProdBtn',false);
      show('selectionBox',false);
      show('trialSection',false);
      return;
    }
    if(snapshot.postMaintenanceObservation){
      q('bestTitle').textContent='Post-maintenance observation · '+snapshot.observedContainers+' / '+snapshot.targetContainers;
      q('bestWhy').textContent='The synthetic production source has resumed after '+(snapshot.workOrderId||'maintenance')+'. LineAlert is observing a short healthy-reference window before re-enabling normal production interpretation. This observation does not authorize return to service, prove the maintenance succeeded, or provide safety approval.';
      q('nextBtn').textContent='Observing · no LineAlert action';
      q('nextBtn').disabled=true;
      show('returnProdBtn',false);
      show('selectionBox',false);
      show('trialSection',false);
    }
  };

  const baseRenderOps=renderOps;
  renderOps=function(){
    baseRenderOps();
    const snapshot=maintenanceSnapshot();
    if(snapshot.active){
      q('etaExplain').textContent=snapshot.workOrderId+' is active on Labeler 2. LineAlert retains source/event context while normal production interpretation is suspended for the maintained asset.';
      return;
    }
    if(snapshot.postMaintenanceObservation){
      q('etaExplain').textContent='Maintenance is complete for '+(snapshot.workOrderId||'Labeler 2')+'. Normal LineAlert production interpretation remains paused until the synthetic post-maintenance observation window completes.';
    }
  };

  const baseUpdateSpeedControl=updateSpeedControl;
  updateSpeedControl=function(){
    const snapshot=maintenanceSnapshot();
    if(snapshot.active){
      q('speedBtn').disabled=false;
      q('speedBtn').textContent=fast?'⏩ FAST FORWARD · MAINTENANCE':'⏩ Complete maintenance window';
      q('speedNote').textContent='Active maintenance on Labeler 2 · normal production interpretation is paused. Demo fast-forward advances only to the end of this synthetic work order.';
      return;
    }
    if(snapshot.postMaintenanceObservation){
      q('speedBtn').disabled=true;
      q('speedBtn').textContent='● 1× POST-MAINTENANCE OBSERVE';
      q('speedNote').textContent='Watching '+snapshot.observedContainers+' / '+snapshot.targetContainers+' synthetic production containers before normal interpretation resumes.';
      return;
    }
    return baseUpdateSpeedControl();
  };

  const button=q('speedBtn');
  if(button){
    const baseSpeedClick=button.onclick;
    button.onclick=function(){
      const snapshot=maintenanceSnapshot();
      if(snapshot.active){
        fastEvent={id:snapshot.workOrderId,title:snapshot.title,time:snapshot.end};
        fastTarget=Math.max(simAbs,snapshot.end+1);
        fast=true;
        q('speedBtn').textContent='⏩ FAST FORWARD · MAINTENANCE';
        q('speedNote').textContent='Accelerating the synthetic clock to maintenance completion. No production findings are evaluated during this interval.';
        return;
      }
      if(snapshot.postMaintenanceObservation)return;
      return baseSpeedClick?baseSpeedClick.call(button):undefined;
    };
  }

  window.LineAlertMaintenanceObserve={
    STATE_KEY,
    snapshot:maintenanceSnapshot,
    postMaintenanceTarget:POST_MAINT_TARGET
  };

  syncLifecycle();
  schedule();
  updateModeLabels();
  renderHero();
  renderOps();
  updateSpeedControl();
})();
