(function(){
  'use strict';

  const SIM_SECONDS_PER_SEQUENCE=10;
  const button=document.getElementById('speedBtn');
  if(!button)return;

  let lastEventSequence=0;
  let sourceEvents=[];
  let clockAnchor=null;
  let lastClockSequence=null;
  let pendingTarget=null;
  let pendingKind=null;
  let controlPending=false;
  let controlError=null;
  let recordedConcernId=null;

  const priorUpdateSpeedControl=updateSpeedControl;
  const priorSpeedClick=button.onclick;

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

  function activeEpisode(){
    try{return !!(incident||mode==='diagnostic'||productionVerification||trialInProgress);}
    catch(_){return true;}
  }

  function sourceTimeFor(plantSequence){
    if(!Number.isFinite(clockAnchor)||!Number.isFinite(Number(plantSequence)))return simAbs;
    return clockAnchor+Number(plantSequence)*SIM_SECONDS_PER_SEQUENCE;
  }

  function renderAssetSourceState(status){
    if(!status||!status.active)return;
    const runState=Number(status.runStateCode);
    const modeTop=document.getElementById('modeTop');
    if(modeTop){
      if(runState===0)modeTop.textContent='LABELER 2 STOPPED · OPC UA CONNECTED';
      else if(runState===2)modeTop.textContent='LABELER 2 DIAGNOSTIC RUN · OPC UA CONNECTED';
      else if(runState===1)modeTop.textContent='LABELER 2 RUNNING · OPC UA CONNECTED';
    }
  }

  function syncClockToSource(){
    const status=sourceStatus();
    if(!status||!status.active||!Number.isFinite(Number(status.sourceSequence)))return;
    const sequence=Number(status.sourceSequence);
    if(lastClockSequence===null||sequence<lastClockSequence){
      clockAnchor=simAbs-sequence*SIM_SECONDS_PER_SEQUENCE;
      if(lastClockSequence!==null&&sequence<lastClockSequence){
        lastEventSequence=0;
        sourceEvents=[];
        recordedConcernId=null;
      }
    }
    if(Number.isFinite(clockAnchor)){
      const desired=clockAnchor+sequence*SIM_SECONDS_PER_SEQUENCE;
      if(desired>simAbs){
        simAbs=desired;
        try{clock();renderTicketHistory();}catch(_){}
      }else if(simAbs-desired>SIM_SECONDS_PER_SEQUENCE){
        clockAnchor=simAbs-sequence*SIM_SECONDS_PER_SEQUENCE;
      }
    }
    lastClockSequence=sequence;
    if(pendingTarget!==null&&sequence>=pendingTarget){
      pendingTarget=null;
      pendingKind=null;
      controlPending=false;
      controlError=null;
      updateSpeedControl();
    }
    renderAssetSourceState(status);
  }

  function normalizeEvent(event){
    const plantSequence=Number(event&&event.plant_sequence);
    const eventSequence=Number(event&&event.source_event_sequence);
    if(!Number.isFinite(plantSequence)||!Number.isFinite(eventSequence))return null;
    return Object.assign({},event,{
      plant_sequence:plantSequence,
      source_event_sequence:eventSequence,
      time:sourceTimeFor(plantSequence)
    });
  }

  function appendSourceEvent(event){
    const normalized=normalizeEvent(event);
    if(!normalized)return;
    sourceEvents.push(normalized);
    sourceEvents=sourceEvents.slice(-240);
    if(window.LineAlertEventJournal&&window.LineAlertEventJournal.append){
      try{
        window.LineAlertEventJournal.append({
          time:normalized.time,
          source:normalized.source,
          eventClass:normalized.event_class,
          severity:normalized.severity||'Information',
          asset:normalized.asset||'Labeler 2',
          message:normalized.message,
          clockQuality:'deterministic_simulator_sequence',
          classification:'synthetic_demo_only',
          fields:Object.assign({},normalized.fields||{}, {
            source_event_sequence:normalized.source_event_sequence,
            plant_sequence:normalized.plant_sequence,
            simulated_elapsed_seconds:normalized.simulated_elapsed_seconds
          })
        });
      }catch(_){}
    }
  }

  function recordConcernIfNeeded(){
    try{
      if(!opcActive()||!incident||!currentIncident)return;
      const id=String(currentIncident.id||'');
      if(!id.startsWith('OPC-L2-')||recordedConcernId===id)return;
      recordedConcernId=id;
      const status=sourceStatus();
      if(window.LineAlertEventJournal&&window.LineAlertEventJournal.append){
        window.LineAlertEventJournal.append({
          time:currentIncident.time,
          source:'linealert/deterministic-opc',
          eventClass:'CONCERN',
          severity:'Notice',
          asset:'Labeler 2',
          message:'Qualified OPC UA evidence crossed the Labeler 2 concern gate',
          clockQuality:'qualified_source_plus_simulator_clock',
          classification:'synthetic_demo_only',
          fields:{
            incident_id:id,
            plant_sequence:status&&status.sourceSequence,
            boundary:'threshold_crossing_is_not_diagnosis'
          }
        });
      }
    }catch(_){}
  }

  async function pollPlantEvents(){
    try{
      if(opcActive()){
        const response=await fetch('/api/plant-events?after='+encodeURIComponent(lastEventSequence),{
          cache:'no-store'
        });
        if(response.ok){
          const payload=await response.json();
          const events=Array.isArray(payload.events)?payload.events:[];
          events.sort((a,b)=>Number(a.source_event_sequence)-Number(b.source_event_sequence));
          events.forEach(event=>{
            const eventSequence=Number(event.source_event_sequence);
            if(!Number.isFinite(eventSequence)||eventSequence<=lastEventSequence)return;
            appendSourceEvent(event);
            lastEventSequence=eventSequence;
          });
          controlError=null;
        }
      }
    }catch(err){
      controlError=err&&err.message?err.message:'plant event feed unavailable';
    }finally{
      window.setTimeout(pollPlantEvents,500);
    }
  }

  async function fastForwardSource(){
    const status=sourceStatus();
    if(!status||!status.active||status.runStateCode!==1||activeEpisode()||controlPending)return;
    controlPending=true;
    controlError=null;
    updateSpeedControl();
    try{
      const response=await fetch('/api/demo-control',{
        method:'POST',
        cache:'no-store',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({action:'fast_forward_to_next_concern'})
      });
      const payload=await response.json();
      if(!response.ok||payload.accepted===false){
        throw new Error(payload.reason||('simulator control '+response.status));
      }
      pendingTarget=Number.isFinite(Number(payload.target_sequence))
        ?Number(payload.target_sequence)
        :null;
      pendingKind=payload.target_kind||null;
      if(pendingTarget===null)controlPending=false;
    }catch(err){
      controlPending=false;
      controlError=err&&err.message?err.message:'source fast-forward failed';
    }
    updateSpeedControl();
  }

  function renderSourceSpeedControl(){
    const status=sourceStatus();
    if(!status||!status.everActivated)return false;
    priorUpdateSpeedControl();
    if(!status.active||status.suspended)return true;
    renderAssetSourceState(status);

    if(controlPending||pendingTarget!==null){
      button.disabled=true;
      button.textContent='⏩ ADVANCING SOURCE';
      const note=document.getElementById('speedNote');
      if(note){
        note.textContent=pendingKind==='concern_precursor'
          ?'Moving Labeler 2 simulator time to the next concern precursor…'
          :'Moving Labeler 2 simulator time to the next consequential roll-change window…';
      }
      return true;
    }

    const runState=Number(status.runStateCode);
    const blocked=activeEpisode()||runState!==1;
    button.disabled=blocked;
    button.textContent=blocked?'● SOURCE TIME':'⏩ Fast-forward to next concern precursor';
    const note=document.getElementById('speedNote');
    if(note){
      if(controlError){
        note.textContent='Source pacing request failed: '+controlError;
      }else if(activeEpisode()){
        note.textContent='Active workflow · source fast-forward is paused until the episode is resolved.';
      }else if(runState===0){
        note.textContent='Labeler 2 changeover or stop is in progress; source pacing is temporarily unavailable.';
      }else if(runState===2){
        note.textContent='Diagnostic run in progress; source fast-forward is unavailable.';
      }else{
        note.textContent='Plant time follows the Labeler 2 simulator. Fast-forward lands before the next consequential changeover so the precursor can unfold through OPC UA.';
      }
    }
    return true;
  }

  updateSpeedControl=function(){
    if(renderSourceSpeedControl())return;
    return priorUpdateSpeedControl();
  };

  button.onclick=function(event){
    if(opcActive())return fastForwardSource();
    if(priorSpeedClick)return priorSpeedClick.call(button,event);
  };

  window.LineAlertOpcuaPlantOrchestration={
    status:function(){
      return {
        lastEventSequence,
        clockAnchor,
        pendingTarget,
        controlPending,
        controlError
      };
    },
    latestRollChangeBefore:function(plantSequence){
      const limit=Number.isFinite(Number(plantSequence))?Number(plantSequence):Infinity;
      const matches=sourceEvents.filter(event=>
        event.plant_sequence<=limit&&
        event.source==='synthetic-cmms/labeler2'&&
        event.message==='Label roll change completed'
      );
      return matches.length?matches[matches.length-1]:null;
    }
  };

  window.setInterval(function(){
    if(!opcActive())return;
    syncClockToSource();
    recordConcernIfNeeded();
    updateSpeedControl();
  },250);
  pollPlantEvents();
})();
