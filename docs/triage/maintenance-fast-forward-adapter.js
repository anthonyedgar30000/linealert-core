(function(){
  'use strict';

  const button=document.getElementById('speedBtn');
  if(
    !button||
    typeof jobPlan!=='function'||
    typeof shiftAt!=='function'||
    typeof nextShift!=='function'||
    typeof findNextIncident!=='function'||
    typeof updateSpeedControl!=='function'
  )return;

  const TARGET_ASSET='Labeler 2';
  const LOOKAHEAD_SHIFTS=90;
  const baseUpdateSpeedControl=updateSpeedControl;
  const baseSpeedClick=button.onclick;

  function nextMaintenance(afterAbs){
    let shift=shiftAt(afterAbs);
    for(let i=0;i<LOOKAHEAD_SHIFTS;i++){
      const work=jobPlan(shift)
        .filter(job=>job.asset===TARGET_ASSET&&job.start>afterAbs)
        .sort((a,b)=>a.start-b.start)[0];
      if(work)return work;
      shift=nextShift(shift);
    }
    return null;
  }

  function maintenanceComesFirst(afterAbs){
    const work=nextMaintenance(afterAbs);
    if(!work)return null;
    const incidentCandidate=findNextIncident(afterAbs);
    const incidentPreview=incidentCandidate?incidentCandidate.time-PREVIEW_LEAD:Infinity;
    return work.start<incidentPreview?work:null;
  }

  updateSpeedControl=function(){
    baseUpdateSpeedControl();
    const lifecycle=window.LineAlertMaintenanceObserve?
      window.LineAlertMaintenanceObserve.snapshot():null;
    if(lifecycle&&(lifecycle.active||lifecycle.postMaintenanceObservation))return;
    if(incident||mode==='diagnostic'||productionVerification||fast)return;

    const work=maintenanceComesFirst(simAbs+1);
    if(!work)return;
    button.disabled=false;
    button.textContent='⏩ Speed up to next plant event';
    q('speedNote').textContent='Next plant event: '+work.id+' · '+TARGET_ASSET+
      ' maintenance at '+fmt(work.start)+'. Fast-forward will stop there before any later incident.';
  };

  button.onclick=function(){
    const lifecycle=window.LineAlertMaintenanceObserve?
      window.LineAlertMaintenanceObserve.snapshot():null;
    if(lifecycle&&(lifecycle.active||lifecycle.postMaintenanceObservation)){
      return baseSpeedClick?baseSpeedClick.call(button):undefined;
    }
    if(incident||mode==='diagnostic'||productionVerification){
      return baseSpeedClick?baseSpeedClick.call(button):undefined;
    }

    if(window.LineAlertRecoveryFastForward){
      window.LineAlertRecoveryFastForward.leaveRecoveredEpisodeForAdvance();
      window.LineAlertRecoveryFastForward.clearFastForwardState();
    }

    const work=maintenanceComesFirst(simAbs+1);
    if(!work)return baseSpeedClick?baseSpeedClick.call(button):undefined;

    fastEvent={id:work.id,title:work.title,time:work.start};
    fastTarget=work.start;
    fast=true;
    button.textContent='⏩ FAST FORWARD · PLANT EVENT';
    q('speedNote').textContent='Accelerating calendar, production, crew workload and CMMS queue together; '+
      'automatic handoff at '+work.id+' maintenance start.';
  };

  window.LineAlertMaintenanceFastForward={
    nextMaintenance,
    maintenanceComesFirst
  };

  updateSpeedControl();
})();
