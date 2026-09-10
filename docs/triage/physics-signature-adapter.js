(function(){
  'use strict';
  const physics=window.LineAlertRollPhysics,model=window.LineAlertPlantEventModel;
  if(!physics||!model)return;

  let originalGuideAction=null;
  function esc(value){return String(value==null?'':value).replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));}
  function currentIncidentSafe(){try{return typeof currentIncident!=='undefined'?currentIncident:null;}catch(_){return null;}}
  function currentTimeSafe(inc){try{return typeof simAbs!=='undefined'&&Number.isFinite(simAbs)?simAbs:inc.time;}catch(_){return inc.time;}}
  function actionsSafe(){try{return typeof actions!=='undefined'?actions:null;}catch(_){return null;}}
  function incidentEvents(inc){
    const events=model.generatedEvents(inc.time,12*model.H,0);
    return events.filter(e=>e.fields&&((e.fields.relatedIncidentId===inc.id)||(e.fields.incidentId===inc.id)));
  }
  function findSequence(inc){
    const events=incidentEvents(inc).slice().sort((a,b)=>a.time-b.time);
    const change=events.find(e=>e.eventClass==='CHANGEOVER'&&e.asset==='Labeler 2');
    const restart=events.find(e=>e.message==='Production resumed after recorded roll change');
    const signature=events.find(e=>e.eventClass==='SIGNATURE');
    const presentation=events.find(e=>e.eventClass==='TELEMETRY'&&e.fields&&e.fields.signal==='presentation_interval_stddev_ms');
    const strong=!!(change&&restart&&signature&&presentation&&change.time<=restart.time&&restart.time<signature.time&&signature.time<presentation.time&&presentation.time<=inc.time);
    const moderate=!strong&&!!(change&&presentation&&change.time<presentation.time&&presentation.time<=inc.time);
    return{events,change,restart,signature,presentation,level:strong?'STRONG':moderate?'MODERATE':'CONTEXT'};
  }
  function ensureAnchorCard(){
    const old=document.getElementById('physicsSignatureCard');if(old)old.remove();
    let card=document.getElementById('investigationAnchorCard');
    if(card)return card;
    const anchor=document.getElementById('recentRecordedContext')||document.getElementById('assetSummary');
    if(!anchor)return null;
    card=document.createElement('div');card.id='investigationAnchorCard';card.className='hidden';
    card.style.cssText='margin:10px 0 12px;padding:11px 12px;border:1px solid #d8dfda;border-radius:12px;background:#f8faf8';
    anchor.insertAdjacentElement('afterend',card);return card;
  }
  function ensureCommonChecks(){
    let box=document.getElementById('rollChangeCommonChecks');if(box)return box;
    const why=document.getElementById('bestWhy');if(!why)return null;
    box=document.createElement('div');box.id='rollChangeCommonChecks';box.className='hidden';
    box.style.cssText='margin:9px 0 10px;padding:9px 10px;border:1px solid #dce3de;border-radius:10px;background:#fff;font-size:.76rem;line-height:1.4;color:#536159';
    why.insertAdjacentElement('afterend',box);return box;
  }
  function ensureAnalystEvidence(){
    let panel=document.getElementById('physicsAnalystEvidence');if(panel)return panel;
    const evidence=document.querySelector('#labelerPanel .details details');if(!evidence)return null;
    panel=document.createElement('details');panel.id='physicsAnalystEvidence';panel.className='hidden';
    panel.style.cssText='margin-top:9px;padding-top:8px;border-top:1px solid #e4e9e5';
    evidence.appendChild(panel);return panel;
  }
  function metric(label,value,sub){return '<div style="padding:7px;border:1px solid #e0e6e2;border-radius:9px;background:#fff"><span style="display:block;font-size:.55rem;font-weight:900;letter-spacing:.08em;color:#748078">'+esc(label)+'</span><b style="display:block;margin-top:2px;font-size:.8rem">'+esc(value)+'</b>'+(sub?'<small style="display:block;margin-top:2px;color:#748078">'+esc(sub)+'</small>':'')+'</div>';}
  function setGuideAction(active){
    const set=actionsSafe();if(!set||!set.guide)return;
    if(!originalGuideAction)originalGuideAction={title:set.guide.title,why:set.guide.why};
    if(active){
      set.guide.title='Check roll loading + web path against approved changeover reference';
      set.guide.why='The recorded roll change is the strongest investigation anchor because a coupled machine-behavior pattern emerged after restart and presentation variability followed later.';
    }else if(originalGuideAction){
      set.guide.title=originalGuideAction.title;set.guide.why=originalGuideAction.why;
    }
  }
  function refreshHero(){try{if(typeof renderHero==='function')renderHero();}catch(_){} }
  function render(){
    const anchor=ensureAnchorCard(),checks=ensureCommonChecks(),analyst=ensureAnalystEvidence();
    const inc=currentIncidentSafe();
    if(!inc||inc.kind!=='guide'||!Number.isFinite(inc.time)){
      if(anchor)anchor.classList.add('hidden');if(checks)checks.classList.add('hidden');if(analyst)analyst.classList.add('hidden');
      setGuideAction(false);refreshHero();return;
    }
    const seq=findSequence(inc),now=currentTimeSafe(inc),signatureVisible=seq.signature&&now>=seq.signature.time;
    const weighted=signatureVisible&&seq.level==='STRONG';
    setGuideAction(weighted);refreshHero();

    if(anchor){
      const changeLead=seq.change?Math.max(0,Math.round((inc.time-seq.change.time)/60)):null;
      const summary=weighted
        ?'Recorded roll change → production restart → coupled machine-behavior signature → later presentation deviation. That sequence makes the changeover the strongest place to begin the investigation; it does not establish cause.'
        :'The recorded roll change remains recent context. LineAlert has not yet accumulated the full configured evidence sequence needed to weight it strongly.';
      anchor.innerHTML='<span style="display:block;font-size:.6rem;font-weight:900;letter-spacing:.1em;color:#69756f">INVESTIGATION ANCHOR · '+esc(weighted?'STRONG':seq.level)+'</span>'+
        '<b style="display:block;margin:5px 0 3px">Recent label-roll change</b>'+
        '<small style="display:block;color:#69756f;line-height:1.4">'+esc(summary)+(changeLead==null?'':' · '+changeLead+' min before concern')+'</small>'+
        '<small style="display:block;margin-top:5px;color:#69756f">Investigation priority ≠ causal probability · signature match ≠ diagnosis.</small>';
      anchor.classList.remove('hidden');
    }
    if(checks){
      if(weighted){
        checks.innerHTML='<b style="display:block;margin-bottom:4px;color:#17211c">Check first</b>Roll seated / centered · web follows the approved thread path · guide / spacing matches the marked setup reference · web tracks without obvious drag or sideways pull.<small style="display:block;margin-top:5px;color:#748078">Illustrative generic demo checks only. Observe first; correct only a confirmed mismatch under the authorized client / OEM procedure. Pictures can be commissioned later.</small>';
        checks.classList.remove('hidden');
      }else checks.classList.add('hidden');
    }
    if(analyst&&seq.restart&&seq.signature){
      const elapsed=Math.max(0,Math.min(inc.time-seq.restart.time,now-seq.restart.time));
      const severity=physics.severityForIncident(inc.id),cmp=physics.comparison(elapsed,severity),p=cmp.problem,h=cmp.healthy;
      const detectionLead=Math.max(0,Math.round((inc.time-seq.signature.time)/60));
      analyst.innerHTML='<summary style="cursor:pointer;font-size:.72rem;font-weight:850">Analyst evidence · synthetic signal model</summary>'+
        '<small style="display:block;margin:6px 0;color:#69756f;line-height:1.45">This is the behind-the-scenes evidence used to weight the recent changeover. It is not operator-facing machine truth.</small>'+
        '<div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px">'+
          metric('ROTATION',p.rpm.toFixed(0)+' rpm · '+p.rotationalFrequencyHz.toFixed(1)+' Hz','f = RPM / 60')+
          metric('1× VIBRATION',p.vibration1xMmS.toFixed(2)+' mm/s RMS','healthy '+h.vibration1xMmS.toFixed(2)+' · ratio '+cmp.vibrationRatio.toFixed(2)+'×')+
          metric('WEB TENSION MOD',p.tensionPeakToPeakN.toFixed(2)+' N p-p','healthy '+h.tensionPeakToPeakN.toFixed(2)+' N p-p')+
          metric('MOTOR CURRENT MOD',p.currentPeakToPeakA.toFixed(2)+' A p-p','healthy '+h.currentPeakToPeakA.toFixed(2)+' A p-p')+
        '</div><small style="display:block;margin-top:7px;color:#69756f;line-height:1.45">Signature became distinguishable about '+detectionLead+' min before the concern. f = RPM / 60 · ω = 2πf · F = m·e·ω² · T ≈ torque / radius · I ≈ torque / Kt. Force-to-vibration gain remains synthetic because real structure and sensor mounting are not commissioned.</small>';
      analyst.classList.remove('hidden');
    }else if(analyst)analyst.classList.add('hidden');
  }

  render();setInterval(render,500);
})();
