(function(){
  'use strict';
  const physics=window.LineAlertRollPhysics,model=window.LineAlertPlantEventModel;
  if(!physics||!model)return;

  function esc(value){return String(value==null?'':value).replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));}
  function ensureCard(){
    let card=document.getElementById('physicsSignatureCard');
    if(card)return card;
    const anchor=document.getElementById('recentRecordedContext')||document.getElementById('assetSummary');
    if(!anchor)return null;
    card=document.createElement('div');
    card.id='physicsSignatureCard';
    card.className='hidden';
    card.style.cssText='margin:10px 0 12px;padding:12px;border:1px solid #ccd7cf;border-radius:12px;background:#f7faf8';
    anchor.insertAdjacentElement('afterend',card);
    return card;
  }
  function currentIncidentSafe(){try{return typeof currentIncident!=='undefined'?currentIncident:null;}catch(_){return null;}}
  function currentTimeSafe(inc){try{return typeof simAbs!=='undefined'&&Number.isFinite(simAbs)?simAbs:inc.time;}catch(_){return inc.time;}}
  function incidentEvents(inc){
    const events=model.generatedEvents(inc.time,12*model.H,0);
    return events.filter(e=>e.fields&&((e.fields.relatedIncidentId===inc.id)||(e.fields.incidentId===inc.id)));
  }
  function metric(label,value,sub){return '<div style="padding:7px;border:1px solid #e0e6e2;border-radius:9px;background:#fff"><span style="display:block;font-size:.55rem;font-weight:900;letter-spacing:.08em;color:#748078">'+esc(label)+'</span><b style="display:block;margin-top:2px;font-size:.8rem">'+esc(value)+'</b>'+(sub?'<small style="display:block;margin-top:2px;color:#748078">'+esc(sub)+'</small>':'')+'</div>';}
  function render(){
    const card=ensureCard();if(!card)return;
    const inc=currentIncidentSafe();
    if(!inc||inc.kind!=='guide'||!Number.isFinite(inc.time)){card.classList.add('hidden');return;}
    const events=incidentEvents(inc);
    const restart=events.find(e=>e.message==='Production resumed after recorded roll change');
    const detected=events.find(e=>e.eventClass==='SIGNATURE');
    if(!restart||!detected){card.classList.add('hidden');return;}
    const now=currentTimeSafe(inc),elapsed=Math.max(0,Math.min(inc.time-restart.time,now-restart.time));
    const severity=physics.severityForIncident(inc.id),cmp=physics.comparison(elapsed,severity),p=cmp.problem,h=cmp.healthy;
    const visible=now>=detected.time;
    const state=now<restart.time?'WAITING FOR RESTART':visible?'SYNTHETIC SIGNATURE VISIBLE':'SETTLING · BELOW SIGNATURE RULE';
    const detectionLead=Math.max(0,Math.round((inc.time-detected.time)/60));
    card.innerHTML='<span style="display:block;font-size:.6rem;font-weight:900;letter-spacing:.1em;color:#69756f">PHYSICS-INFORMED SYNTHETIC SIGNATURE</span>'+
      '<b style="display:block;margin:5px 0 2px">'+esc(state)+'</b>'+
      '<small style="display:block;color:#69756f;line-height:1.4">One illustrative setup disturbance drives the coupled RPM / 1× vibration / web-tension / motor-current pattern. Calculated values are demo evidence, not an OEM model or verified physical state.</small>'+
      '<div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px;margin-top:9px">'+
        metric('ROTATION',p.rpm.toFixed(0)+' rpm · '+p.rotationalFrequencyHz.toFixed(1)+' Hz','f = RPM / 60')+
        metric('1× VIBRATION',p.vibration1xMmS.toFixed(2)+' mm/s RMS','healthy ref '+h.vibration1xMmS.toFixed(2)+' · ratio '+cmp.vibrationRatio.toFixed(2)+'×')+
        metric('WEB TENSION MOD',p.tensionPeakToPeakN.toFixed(2)+' N p-p','healthy ref '+h.tensionPeakToPeakN.toFixed(2)+' N p-p')+
        metric('MOTOR CURRENT MOD',p.currentPeakToPeakA.toFixed(2)+' A p-p','healthy ref '+h.currentPeakToPeakA.toFixed(2)+' A p-p')+
      '</div>'+
      '<small style="display:block;margin-top:8px;color:#69756f">'+(visible?'Signature rule became distinguishable about '+detectionLead+' min before the concern threshold. ':'Current synthetic signal shape has not yet met the configured coupled-signature rule. ')+'Model match ≠ diagnosis · historical pattern ≠ current root cause.</small>'+
      '<details style="margin-top:7px"><summary style="cursor:pointer;font-size:.72rem;font-weight:850">Show calculator relationships</summary><small style="display:block;margin-top:6px;color:#69756f;line-height:1.55">f = RPM / 60 · ω = 2πf · rotating unbalance force F = m·e·ω² · approximate web tension T = torque / radius · approximate motor current I = torque / Kt. The force-to-vibration transfer gain is synthetic because structure mass, stiffness, damping, resonance and sensor mounting are not commissioned.</small></details>';
    card.classList.remove('hidden');
  }

  render();
  setInterval(render,500);
})();
