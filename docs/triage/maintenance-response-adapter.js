(function(){
  'use strict';

  if(typeof maintenanceEta!=='function'||typeof schedule!=='function'||typeof renderOps!=='function'||typeof opsSnapshot!=='function')return;

  function qualifiedAvailabilityEta(abs){
    const snap=opsSnapshot(abs);
    const idle=snap.techs.find(t=>!t.active);
    if(idle)return 5;
    return 5+Math.min(...snap.techs.map(t=>t.freeIn));
  }

  function responseSnapshot(abs){
    return {
      dispatchRecorded:false,
      availabilityEtaMinutes:qualifiedAvailabilityEta(abs),
      availabilitySource:'synthetic_crew_occupancy'
    };
  }

  // Diagnostic workflow state is not evidence that maintenance has been dispatched.
  // Preserve crew-derived availability, but remove the baseline mode==='diagnostic'
  // shortcut that converted investigation state into a zero-minute maintenance ETA.
  maintenanceEta=qualifiedAvailabilityEta;

  const baseSchedule=schedule;
  schedule=function(){
    baseSchedule();
    if(mode!=='diagnostic')return;
    q('maintLabel').textContent='MAINTENANCE SUPPORT';
    q('maintEta').textContent='Not dispatched';
    q('assetEtaLabel').textContent='MAINT';
    q('assetEta').textContent='Not dispatched';
  };

  const baseRenderOps=renderOps;
  renderOps=function(){
    baseRenderOps();
    if(mode!=='diagnostic')return;
    const response=responseSnapshot(simAbs);
    q('etaExplain').textContent='No maintenance dispatch is recorded for this concern. Next qualified maintenance availability estimate: '+response.availabilityEtaMinutes+' min.';
  };

  window.LineAlertMaintenanceResponse={snapshot:()=>responseSnapshot(simAbs)};
  schedule();
  renderOps();
})();
