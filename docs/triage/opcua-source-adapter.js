(function(){
  'use strict';

  const PROFILE='linealert-labeler2-observable-v1';
  const ASSET='Labeler 2';
  const REQUIRED=[
    'emulator_sequence',
    'run_state_code',
    'line_speed_cpm',
    'presentation_interval_stddev_ms',
    'camera_observed_containers',
    'camera_aligned_containers',
    'apparent_skew_events',
    'max_abs_alignment_offset_mm',
    'accepted_containers',
    'reject_candidates',
    'roll_change_recent'
  ];
  const PRESENTATION_CONCERN_MS=16.0;
  const MIN_CAMERA_BATCH=5;
  const MAX_ALIGNED_RATIO_FOR_CONCERN=0.8;

  let everActivated=false;
  let active=false;
  let suspended=false;
  let latest=null;
  let lastSourceSequence=null;
  let lastTrialSequence=null;
  let lastVerificationSequence=null;
  let sourceConcernLatched=false;
  let pendingSourceTrial=null;

  const browserLive=live;
  const browserMaybeTriggerIncident=maybeTriggerIncident;
  const browserUpdateSpeedControl=updateSpeedControl;

  function el(id){return document.getElementById(id);}

  function ensureBanner(){
    let banner=el('machineEvidenceSourceBanner');
    if(banner)return banner;
    banner=document.createElement('div');
    banner.id='machineEvidenceSourceBanner';
    banner.style.cssText=[
      'margin:0 0 16px',
      'padding:10px 13px',
      'border:1px solid #cfd8d2',
      'border-radius:12px',
      'background:#f8faf8',
      'display:flex',
      'justify-content:space-between',
      'gap:14px',
      'align-items:center',
      'font-size:.75rem'
    ].join(';');
    banner.innerHTML='<div><b id="machineEvidenceSourceState">SOURCE · SCENARIO PREVIEW</b><small id="machineEvidenceSourceDetail" style="display:block;margin-top:2px;color:#66716b">Browser-generated machine evidence is active because no qualified local Labeler OPC UA source has been admitted.</small></div><span id="machineEvidenceSourceScope" class="pill">synthetic preview</span>';
    const status=document.querySelector('.status');
    if(status)status.insertAdjacentElement('beforebegin',banner);
    return banner;
  }

  function setBanner(state,detail,scope){
    ensureBanner();
    const stateEl=el('machineEvidenceSourceState');
    const detailEl=el('machineEvidenceSourceDetail');
    const scopeEl=el('machineEvidenceSourceScope');
    if(stateEl)stateEl.textContent=state;
    if(detailEl)detailEl.textContent=detail;
    if(scopeEl)scopeEl.textContent=scope;
  }

  function signal(payload,name){
    const item=payload&&payload.signals?payload.signals[name]:null;
    if(!item||item.quality!=='good')return null;
    return item;
  }

  function numeric(payload,name){
    const item=signal(payload,name);
    return item&&Number.isFinite(Number(item.value))?Number(item.value):null;
  }

  function booleanValue(payload,name){
    const item=signal(payload,name);
    return item&&typeof item.value==='boolean'?item.value:null;
  }

  function qualifiedPayload(payload){
    if(!payload||payload.connected!==true)return false;
    if(payload.profile!==PROFILE||payload.asset_id!==ASSET)return false;
    if(payload.source_kind!=='simulator'||payload.source_scope!=='simulator_only')return false;
    if(payload.read_only!==true)return false;
    if(!payload.semantic_admission||payload.semantic_admission.admitted!==true)return false;
    return REQUIRED.every(name=>signal(payload,name)!==null);
  }

  function sourceRunText(code){
    if(code===0)return 'STOPPED · OPC UA EMULATOR';
    if(code===2)return 'DIAGNOSTIC RUN · OPC UA EMULATOR';
    if(code===1)return 'PRODUCTION RUNNING · OPC UA EMULATOR';
    return 'SOURCE STATE UNKNOWN · OPC UA EMULATOR';
  }

  function clearCalendarMachineEpisode(){
    if(!currentIncident||String(currentIncident.id||'').startsWith('OPC-L2-'))return;
    incident=false;
    recoveryObserved=false;
    productionVerification=false;
    currentIncident=null;
    recommendation=null;
    selectedAction='guide';
    lastAction=null;
    iteration=0;
    nextStage='action';
    trialBeforeVar=null;
    trialInProgress=false;
    lastConfirmedTrial=false;
    verificationStreak=0;
    verificationResets=0;
    verificationAccumulator=0;
    handledIncidentIds.clear();
    const history=el('history');
    if(history)history.innerHTML='';
    const concernCount=el('concernCount');
    if(concernCount)concernCount.textContent='0';
    const watchPill=el('watchPill');
    if(watchPill)watchPill.textContent='Normal';
    const labelerNode=el('labelerNode');
    if(labelerNode)labelerNode.classList.remove('watch');
    show('lastTrialCard',false);
    show('verificationCard',false);
    show('trialSection',false);
    show('selectionBox',false);
    renderActions();
  }

  function activate(payload){
    if(!everActivated){
      everActivated=true;
      clearCalendarMachineEpisode();
    }
    active=true;
    suspended=false;
    latest=payload;
    fast=false;
    fastTarget=null;
    fastEvent=null;
    setBanner(
      'SOURCE · LABELER 2 OPC UA EMULATOR · CONNECTED',
      'Qualified read-only simulator evidence is driving machine observations. Plant schedule, staffing and workflow context remain synthetic.',
      'simulator_only · read_only'
    );
    apply(payload);
    renderActions();
    updateSpeedControl();
  }

  function disableWorkflowForUnavailable(){
    ['nextBtn','returnProdBtn','armBtn','hmiBtn'].forEach(id=>{
      const node=el(id);
      if(node)node.disabled=true;
    });
  }

  function markUnavailable(reason){
    if(!everActivated)return;
    active=false;
    suspended=true;
    latest=null;
    setBanner(
      'SOURCE · LABELER 2 OPC UA EMULATOR · UNAVAILABLE',
      'Machine interpretation is paused. Last observations may remain visible only as stale context; the Canvas will not fall back to browser-generated machine evidence.',
      reason||'fail_closed'
    );
    const posture=el('postureTop');
    if(posture)posture.textContent='SOURCE UNAVAILABLE · FAIL CLOSED';
    const runMode=el('modeTop');
    if(runMode)runMode.textContent='MACHINE INTERPRETATION PAUSED';
    const note=el('speedNote');
    if(note)note.textContent='OPC UA source unavailable · machine evidence frozen · browser fallback disabled.';
    const speed=el('speedBtn');
    if(speed){
      speed.disabled=true;
      speed.textContent='SOURCE UNAVAILABLE';
    }
    disableWorkflowForUnavailable();
  }

  function sourceConcern(payload){
    const presentation=numeric(payload,'presentation_interval_stddev_ms');
    const observed=numeric(payload,'camera_observed_containers');
    const aligned=numeric(payload,'camera_aligned_containers');
    if(presentation===null||observed===null||aligned===null||observed<MIN_CAMERA_BATCH)return false;
    return presentation>=PRESENTATION_CONCERN_MS&&(aligned/observed)<=MAX_ALIGNED_RATIO_FOR_CONCERN;
  }

  function makeSourceIncident(payload){
    const presentation=numeric(payload,'presentation_interval_stddev_ms');
    const observed=numeric(payload,'camera_observed_containers');
    const aligned=numeric(payload,'camera_aligned_containers');
    const accepted=numeric(payload,'accepted_containers');
    const quality=observed>0&&accepted!==null?accepted/observed*100:0;
    const sequence=numeric(payload,'emulator_sequence');
    const rollRecent=booleanValue(payload,'roll_change_recent')===true;
    const currentShift=shiftAt(simAbs);
    return {
      id:'OPC-L2-'+String(sequence).padStart(6,'0'),
      shift:currentShift,
      kind:'guide',
      time:simAbs,
      title:'Alignment variability in qualified Labeler 2 emulator evidence',
      summary:'Presentation variability and camera alignment evidence crossed the configured synthetic investigation gate while the read-only OPC UA source remained qualified.',
      initialVar:presentation,
      quality,
      camera:aligned+' / '+observed+' aligned',
      recommendation:'guide',
      rationale:(rollRecent?'A recent roll-change context is present. ':'')+'The bounded first step remains the approved guide / presentation reference because it is low-disturbance and informative. OPC UA evidence is simulator-only; threshold crossing is not a diagnosis.',
      status:'open'
    };
  }

  function updateEvidenceDom(payload){
    const lineSpeed=numeric(payload,'line_speed_cpm');
    const presentation=numeric(payload,'presentation_interval_stddev_ms');
    const observed=numeric(payload,'camera_observed_containers');
    const aligned=numeric(payload,'camera_aligned_containers');
    const accepted=numeric(payload,'accepted_containers');
    const skew=numeric(payload,'apparent_skew_events');
    const runCode=numeric(payload,'run_state_code');

    if(presentation!==null){
      currentVar=presentation;
      if(el('nodeVar'))el('nodeVar').textContent=presentation.toFixed(1)+' ms';
      if(el('varVal'))el('varVal').textContent=presentation.toFixed(1)+' ms SD';
    }
    if(lineSpeed!==null){
      if(el('labelerRate'))el('labelerRate').textContent=lineSpeed.toFixed(1)+'/min';
      if(el('throughputVal'))el('throughputVal').textContent=lineSpeed.toFixed(1)+'/min';
    }
    ['fillerRate','packerRate','palletRate'].forEach(id=>{
      if(el(id))el(id).textContent='—';
    });
    if(el('fillerCount'))el('fillerCount').textContent='—';
    if(el('palletCount'))el('palletCount').textContent='—';

    if(observed!==null&&aligned!==null&&el('cameraVal')){
      el('cameraVal').textContent=aligned+' / '+observed+' aligned'+(skew!==null?' · '+skew+' skew':'');
    }
    if(observed!==null&&accepted!==null&&el('qualityVal')){
      const pct=observed>0?accepted/observed*100:0;
      el('qualityVal').textContent=accepted+' / '+observed+' accepted · '+pct.toFixed(0)+'%';
    }
    if(runCode!==null&&el('modeTop'))el('modeTop').textContent=sourceRunText(runCode);
    if(el('fillerState'))el('fillerState').textContent='Context · no mapped OPC UA signal';
    if(el('packerState'))el('packerState').textContent='Context · no mapped OPC UA signal';
    if(el('palletizerState'))el('palletizerState').textContent='Context · no mapped OPC UA signal';
    if(el('nodeState')){
      el('nodeState').textContent=runCode===0?'Source reports stopped':runCode===2?'Source reports diagnostic run':'Source reports production';
    }
  }

  function maybeOpenSourceConcern(payload){
    const hasConcern=sourceConcern(payload);
    if(!hasConcern){
      sourceConcernLatched=false;
      return;
    }
    if(sourceConcernLatched||incident||productionVerification||trialInProgress)return;
    sourceConcernLatched=true;
    resetWorkflowForIncident(makeSourceIncident(payload));
    updateEvidenceDom(payload);
    if(window.LineAlertEventJournal){
      try{
        window.LineAlertEventJournal.append({
          type:'source_evidence',
          asset:'Labeler 2',
          title:'Qualified OPC UA evidence crossed the synthetic concern gate',
          detail:'Concern opened from read-only emulator evidence; threshold crossing is not a diagnosis.',
          source:'linealert-labeler2-opcua-local'
        });
      }catch(_){}
    }
  }

  function sourceTrialReady(payload){
    if(!trialInProgress)return false;
    const runCode=numeric(payload,'run_state_code');
    const observed=numeric(payload,'camera_observed_containers');
    const sequence=numeric(payload,'emulator_sequence');
    return runCode===2&&observed!==null&&observed>=5&&sequence!==lastTrialSequence;
  }

  function captureSourceTrial(payload){
    if(!sourceTrialReady(payload))return;
    const sequence=numeric(payload,'emulator_sequence');
    const presentation=numeric(payload,'presentation_interval_stddev_ms');
    const observed=numeric(payload,'camera_observed_containers');
    const aligned=numeric(payload,'camera_aligned_containers');
    const accepted=numeric(payload,'accepted_containers');
    const skew=numeric(payload,'apparent_skew_events');
    if([sequence,presentation,observed,aligned,accepted,skew].some(value=>value===null))return;

    lastTrialSequence=sequence;
    pendingSourceTrial={
      sequence,
      presentation,
      observed,
      aligned,
      accepted,
      skew,
      before:Number.isFinite(trialBeforeVar)?trialBeforeVar:currentVar,
      actionKey:lastAction
    };
    if(el('trialState'))el('trialState').textContent='5 / 5 OPC UA EVIDENCE CAPTURED · READY FOR REVIEW';
    if(el('trialResult')){
      el('trialResult').innerHTML='<p><b>'+accepted+' / '+observed+' accepted · '+aligned+' / '+observed+' aligned · '+skew+' apparent skew</b><br>Presentation variability '+pendingSourceTrial.before.toFixed(1)+' → '+presentation.toFixed(1)+' ms SD.<br>Result came from the qualified read-only emulator source; improvement does not prove mechanism.</p>';
    }
    show('trialResult');
    show('confirmBtn');
    if(el('hmiBtn')){
      el('hmiBtn').disabled=true;
      el('hmiBtn').textContent='OPC UA diagnostic batch captured';
    }
  }

  function confirmSourceTrial(){
    const result=pendingSourceTrial;
    if(!result||!result.actionKey)return;
    const actionTitle=actions[result.actionKey]?actions[result.actionKey].title:result.actionKey;
    if(el('lastTrialAction'))el('lastTrialAction').textContent='Trial '+iteration+' · '+actionTitle;
    if(el('lastAccepted'))el('lastAccepted').textContent=result.accepted+' / '+result.observed+' accepted';
    if(el('lastAligned'))el('lastAligned').textContent=result.aligned+' / '+result.observed+' aligned';
    if(el('lastSkew'))el('lastSkew').textContent=String(result.skew);
    if(el('lastVariation'))el('lastVariation').textContent=result.before.toFixed(1)+' → '+result.presentation.toFixed(1)+' ms';
    if(el('lastInterpretation'))el('lastInterpretation').textContent='Qualified emulator evidence captured after the selected workflow step. Response to an intervention is not causal proof.';
    show('lastTrialCard');

    const history=el('history');
    if(history){
      const row=document.createElement('div');
      row.innerHTML='<b>Trial '+iteration+' · '+actionTitle+'</b><small>OPC UA evidence · '+result.accepted+' / '+result.observed+' accepted · '+result.aligned+' / '+result.observed+' aligned · '+result.before.toFixed(1)+' → '+result.presentation.toFixed(1)+' ms SD. Test response ≠ causal proof.</small>';
      history.appendChild(row);
    }

    show('trialSection',false);
    show('selectionBox',false);
    trialInProgress=false;
    lastConfirmedTrial=true;
    pendingSourceTrial=null;
    const qualifies=result.presentation<=VERIFY_VAR_MAX&&result.aligned===result.observed&&result.accepted===result.observed;
    if(qualifies){
      recommendation='repeat';
      nextStage='action';
      selectedAction='repeat';
    }else{
      recommendation='guide';
      nextStage='action';
      selectedAction='guide';
    }
    renderActions();
  }

  function countVerification(payload){
    if(!productionVerification)return;
    const runCode=numeric(payload,'run_state_code');
    const sequence=numeric(payload,'emulator_sequence');
    const presentation=numeric(payload,'presentation_interval_stddev_ms');
    const observed=numeric(payload,'camera_observed_containers');
    const aligned=numeric(payload,'camera_aligned_containers');
    const accepted=numeric(payload,'accepted_containers');
    if(runCode!==1||sequence===null||sequence===lastVerificationSequence)return;
    if([presentation,observed,aligned,accepted].some(value=>value===null)||observed<=0)return;

    lastVerificationSequence=sequence;
    const qualifies=presentation<=VERIFY_VAR_MAX&&aligned===observed&&accepted===observed;
    if(qualifies){
      verificationStreak=Math.min(VERIFY_TARGET,verificationStreak+observed);
    }else{
      verificationStreak=0;
      verificationResets++;
    }
    verificationCameraHealthy=aligned===observed;
    verificationQualityHealthy=accepted===observed;
    renderVerification();
    if(verificationStreak>=VERIFY_TARGET)completeRecovery();
  }

  function apply(payload){
    if(!qualifiedPayload(payload)){
      if(everActivated)markUnavailable(payload&&payload.reason_code);
      return;
    }
    latest=payload;
    active=true;
    suspended=false;
    const sourceSequence=numeric(payload,'emulator_sequence');
    updateEvidenceDom(payload);
    maybeOpenSourceConcern(payload);
    captureSourceTrial(payload);
    if(sourceSequence!==lastSourceSequence){
      lastSourceSequence=sourceSequence;
      countVerification(payload);
    }
  }

  function overrideWorkflowButtons(){
    const hmi=el('hmiBtn');
    if(hmi){
      hmi.onclick=function(){
        if(!everActivated||!trialInProgress)return;
        pendingSourceTrial=null;
        if(el('trialState'))el('trialState').textContent='WAITING FOR EXTERNAL OPC UA DIAGNOSTIC BATCH';
        show('trialResult',false);
        show('confirmBtn',false);
        hmi.disabled=true;
        hmi.textContent='Waiting for emulator / HMI evidence…';
      };
    }
    const confirm=el('confirmBtn');
    if(confirm)confirm.onclick=function(){
      if(everActivated)confirmSourceTrial();
    };
  }

  maybeTriggerIncident=function(){
    if(everActivated)return;
    return browserMaybeTriggerIncident();
  };

  live=function(delta){
    if(everActivated){
      if(latest&&active&&!suspended)apply(latest);
      return;
    }
    return browserLive(delta);
  };

  updateSpeedControl=function(){
    if(everActivated){
      const button=el('speedBtn');
      const note=el('speedNote');
      if(button){
        button.disabled=true;
        button.textContent=active?'● OPC UA SOURCE':'SOURCE UNAVAILABLE';
      }
      if(note){
        note.textContent=active?'Machine evidence follows the external emulator at source cadence; calendar incident fast-forward is disabled.':'Machine evidence is paused until the qualified OPC UA source returns.';
      }
      return;
    }
    return browserUpdateSpeedControl();
  };

  async function poll(){
    try{
      const response=await fetch('/api/telemetry',{cache:'no-store'});
      if(!response.ok)throw new Error('telemetry '+response.status);
      const payload=await response.json();
      if(qualifiedPayload(payload)){
        if(!everActivated){
          activate(payload);
          overrideWorkflowButtons();
        }else{
          active=true;
          suspended=false;
          setBanner(
            'SOURCE · LABELER 2 OPC UA EMULATOR · CONNECTED',
            'Qualified read-only simulator evidence is driving machine observations. Plant schedule, staffing and workflow context remain synthetic.',
            'simulator_only · read_only'
          );
          apply(payload);
          renderHero();
          updateSpeedControl();
        }
      }else if(everActivated){
        markUnavailable(payload&&payload.reason_code);
      }
    }catch(err){
      if(everActivated){
        markUnavailable(err&&err.message?err.message:'EVIDENCE.BRIDGE_UNAVAILABLE');
      }
    }finally{
      window.setTimeout(poll,500);
    }
  }

  ensureBanner();
  setBanner(
    'SOURCE · SCENARIO PREVIEW',
    'Browser-generated machine evidence is active because no qualified local Labeler OPC UA source has been admitted.',
    'synthetic preview'
  );
  window.LineAlertOpcuaSource={
    status:function(){
      return {
        everActivated,
        active,
        suspended,
        profile:latest&&latest.profile||null,
        sourceId:latest&&latest.source_id||null,
        assetId:latest&&latest.asset_id||null,
        runStateCode:latest?numeric(latest,'run_state_code'):null,
        sourceSequence:latest?numeric(latest,'emulator_sequence'):null,
        lastSourceSequence
      };
    }
  };
  poll();
})();
