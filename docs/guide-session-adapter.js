(function(){
  'use strict';
  const store=window.LineAlertDemoSession;
  if(!store)return;
  const MAX_PROJECT_SECONDS=15*60;
  let current=store.load();

  const style=document.createElement('style');
  style.textContent='.sessionStrip{display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin:16px 0}.sessionStrip div{background:#fff;border:1px solid #d7e0da;border-radius:9px;padding:9px}.sessionStrip span{display:block;font:800 9px ui-monospace,monospace;letter-spacing:.07em;color:#68776d}.sessionStrip b{display:block;margin-top:3px;font-size:12px}.card.liveReference{box-shadow:0 0 0 4px rgba(46,139,87,.16)}.syncNote{font-size:11px;color:#61708a;margin-top:8px}@media(max-width:800px){.sessionStrip{grid-template-columns:1fr 1fr}}';
  document.head.appendChild(style);

  const assumption=document.querySelector('.assumption');
  const strip=document.createElement('section');
  strip.className='sessionStrip';
  strip.innerHTML='<div><span>SIM DATE</span><b id="guideSimDate">—</b></div><div><span>SIM TIME</span><b id="guideSimTime">—</b></div><div><span>SHIFT</span><b id="guideShift">—</b></div><div><span>RUN MODE</span><b id="guideRunMode">—</b></div><div><span>SESSION</span><b id="guideSyncState">Waiting</b></div>';
  if(assumption)assumption.insertAdjacentElement('afterend',strip);

  function esc(value){return String(value==null?'':value).replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]))}
  function fmtAbs(abs){
    const d=new Date(abs*1000);
    return {
      date:d.toISOString().slice(0,10),
      time:String(d.getUTCHours()).padStart(2,'0')+':'+String(d.getUTCMinutes()).padStart(2,'0')+':'+String(d.getUTCSeconds()).padStart(2,'0'),
      shift:d.getUTCHours()<6?'NIGHT SHIFT':d.getUTCHours()<14?'DAY SHIFT':d.getUTCHours()<22?'EVENING SHIFT':'NIGHT SHIFT'
    };
  }
  function projected(s){
    if(!s||!Number.isFinite(s.simAbs))return null;
    const elapsed=Math.max(0,Math.min(MAX_PROJECT_SECONDS,Math.floor((Date.now()-(s.updatedAtMs||Date.now()))/1000)));
    const abs=s.simAbs+elapsed;
    return Object.assign({},s,{projectedAbs:abs,projected:fmtAbs(abs)});
  }
  function stateLabel(s){
    if(!s)return 'NO SESSION';
    if(s.recoveryObserved)return 'RECOVERY OBSERVED';
    if(s.productionVerification)return 'PRODUCTION VERIFY';
    if(s.mode==='diagnostic')return 'BOUNDED DIAGNOSTIC';
    if(s.incident)return 'WATCH';
    return 'REFERENCE MODE';
  }
  function recommendedNext(s){
    if(s.productionVerification){
      const v=s.verification||{};
      return 'Continue production verification · '+(v.streak||0)+' / '+(v.target||50)+' consecutive healthy';
    }
    if(s.recoveryObserved)return 'Normal monitoring resumed';
    if(s.recommendationTitle)return s.recommendationTitle;
    return 'No action requested';
  }
  function renderCurrent(s){
    const match=document.querySelector('.match');
    if(!match)return;
    const p=projected(s);
    const dateEl=document.getElementById('guideSimDate'),timeEl=document.getElementById('guideSimTime'),shiftEl=document.getElementById('guideShift'),modeEl=document.getElementById('guideRunMode'),syncEl=document.getElementById('guideSyncState');
    if(!p){
      if(dateEl)dateEl.textContent='—';if(timeEl)timeEl.textContent='—';if(shiftEl)shiftEl.textContent='—';if(modeEl)modeEl.textContent='—';if(syncEl)syncEl.textContent='Open Plant Canvas';
      match.innerHTML='<div class="match-grid"><div><div class="eyebrow">NO SHARED DEMO SESSION YET</div><h2>Reference guide</h2><p>Open the Plant Canvas to start the controlled synthetic plant session. This page will then mirror the same date, shift, incident, evidence and recommended next bounded action.</p><a class="pill" href="./triage/">Open Plant Canvas ↗</a></div><div class="score"><div><span>STATE</span><b>Reference only</b></div><div><span>BOUNDARY</span><b>Synthetic demo</b></div></div></div>';
      updateReferenceCard(null);
      return;
    }
    dateEl.textContent=p.projected.date;timeEl.textContent=p.projected.time;shiftEl.textContent=p.projected.shift;modeEl.textContent=p.runMode||p.mode||'—';syncEl.textContent=stateLabel(p);

    const active=!!(p.incident||p.productionVerification);
    const recovered=!!p.recoveryObserved;
    if(!active&&!recovered){
      match.innerHTML='<div class="match-grid"><div><div class="eyebrow">NO ACTIVE DETECTED ISSUE · REFERENCE MODE</div><h2>Plant operating without an active labeling concern</h2><p>The guide is attached to the same synthetic session as the Plant Canvas. No bounded change is currently being requested.</p><p class="syncNote">'+esc(p.projected.date)+' · '+esc(p.projected.time)+' · '+esc(p.projected.shift)+' · '+esc(p.runMode||'PRODUCTION RUNNING')+'</p></div><div class="score"><div><span>ACTIVE CONCERN</span><b>None</b></div><div><span>PLANT POSTURE</span><b>'+esc(p.posture||'NORMAL · PLAN HOLDS')+'</b></div><div><span>NEXT</span><b>Normal monitoring</b></div></div></div>';
      updateReferenceCard(null);
      return;
    }

    if(recovered&&!active){
      const last=p.currentIncident;
      match.innerHTML='<div class="match-grid"><div><div class="eyebrow">RECOVERY OBSERVED · REFERENCE MODE</div><h2>'+esc(last?last.title:'Previous concern closed')+'</h2><p>The shared Plant Canvas session has closed the concern under its configured production-verification criteria. The guide has returned to reference mode.</p><p><strong>Normal monitoring resumed.</strong></p><p class="syncNote">Recovery observed ≠ root-cause proof or a guarantee of future reliability.</p></div><div class="score"><div><span>INCIDENT</span><b>'+esc(last?last.id:'Closed')+'</b></div><div><span>STATE</span><b>Recovered</b></div><div><span>VERIFICATION</span><b>'+esc((p.verification&&p.verification.target)||50)+' consecutive healthy</b></div><div><span>NEXT</span><b>Normal monitoring</b></div></div></div>';
      updateReferenceCard(last&&last.kind);
      return;
    }

    const inc=p.currentIncident||{};
    const ev=p.evidence||{};
    const latest=p.latestTrial;
    const trialHtml=latest?'<p><strong>Last 5-container trial:</strong> '+esc(latest.actionTitle)+' · '+esc(latest.accepted)+' · '+esc(latest.aligned)+' · presentation '+esc(Number.isFinite(latest.beforeVar)?latest.beforeVar.toFixed(1):'—')+' → '+esc(Number.isFinite(latest.afterVar)?latest.afterVar.toFixed(1):'—')+' ms SD.</p>':'';
    const rationale=p.recommendationWhy||inc.rationale||'Current evidence determines the ranked bounded action; recommendation is advisory.';
    match.innerHTML='<div class="match-grid"><div><div class="eyebrow">CURRENT DETECTED ISSUE · SHARED LIVE DEMO STATE</div><h2>'+esc(inc.title||'Labeling concern')+'</h2><p>'+esc(inc.summary||'The Plant Canvas has an active synthetic concern.')+'</p><p><strong>'+esc(recommendedNext(p))+'</strong></p><p>'+esc(rationale)+'</p>'+trialHtml+'<span class="pill">'+esc(stateLabel(p))+' · '+esc(inc.id||'live concern')+'</span></div><div class="score"><div><span>ASSET</span><b>'+esc(p.asset||'Labeler 2')+'</b></div><div><span>PRESENTATION</span><b>'+esc(ev.presentation||'—')+'</b></div><div><span>CAMERA</span><b>'+esc(ev.camera||'—')+'</b></div><div><span>QUALITY</span><b>'+esc(ev.quality||'—')+'</b></div><div><span>NEXT</span><b>'+esc(recommendedNext(p))+'</b></div></div></div>';
    updateReferenceCard(inc.kind);
  }
  function updateReferenceCard(kind){
    const cards=Array.from(document.querySelectorAll('.card'));
    cards.forEach(c=>c.classList.remove('liveReference'));
    const first=cards[0];
    if(first){
      const standard=first.querySelector('.standard');
      if(kind&&current){
        first.classList.add('liveReference');
        if(standard)standard.innerHTML='<b>Live shared scenario</b>'+esc(recommendedNext(current))+'. The detailed ranking above is driven by the current Plant Canvas session.';
      }else if(standard)standard.innerHTML='<b>Reference note</b>This issue family remains available as a commissioned synthetic reference; no live labeling concern is currently selecting it.';
    }
  }
  function render(){renderCurrent(current)}
  store.subscribe(value=>{current=value;render()});
  render();
  setInterval(render,1000);
})();
