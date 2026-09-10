(function(){
  'use strict';
  const store=window.LineAlertDemoSession;
  if(!store)return;

  function esc(value){
    return String(value==null?'':value).replace(/[&<>"']/g,ch=>({
      '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
    }[ch]));
  }

  function currentMaintenance(){
    const session=store.load();
    return session&&session.maintenance?session.maintenance:null;
  }

  function hasOverlay(match,kind){
    const marker=match.querySelector('[data-linealert-maintenance-view]');
    return !!marker&&marker.dataset.linealertMaintenanceView===kind;
  }

  function apply(){
    const maintenance=currentMaintenance();
    const match=document.querySelector('.match');
    if(!match)return;

    if(!maintenance||(!maintenance.active&&!maintenance.postMaintenanceObservation))return;

    const mode=document.getElementById('guideRunMode');
    const sync=document.getElementById('guideSyncState');
    document.querySelectorAll('.card.liveReference').forEach(card=>card.classList.remove('liveReference'));

    if(maintenance.active){
      if(mode)mode.textContent='MAINTENANCE · OBSERVE ONLY';
      if(sync)sync.textContent='MAINTENANCE';
      if(hasOverlay(match,'active'))return;
      match.innerHTML='<div data-linealert-maintenance-view="active" class="match-grid"><div><div class="eyebrow">MAINTENANCE · NORMAL INTERPRETATION PAUSED</div><h2>Labeler 2 is under maintenance</h2><p>'+esc(maintenance.workOrderId||'Synthetic work order')+' · '+esc(maintenance.title||'Maintenance activity')+'. LineAlert is retaining source and event context but is not applying normal production findings or troubleshooting recommendations to the maintained asset.</p><p><strong>No LineAlert troubleshooting action requested.</strong></p><p class="syncNote">Maintenance activity != verified machine condition.</p></div><div class="score"><div><span>ASSET</span><b>Labeler 2</b></div><div><span>STATE</span><b>Observe only</b></div><div><span>WORK ORDER</span><b>'+esc(maintenance.workOrderId||'Recorded')+'</b></div><div><span>NEXT</span><b>Maintenance completion</b></div></div></div>';
      return;
    }

    const marker='post-'+maintenance.observedContainers;
    if(mode)mode.textContent='POST-MAINTENANCE OBSERVATION';
    if(sync)sync.textContent='POST-MAINT OBSERVE';
    if(hasOverlay(match,marker))return;
    match.innerHTML='<div data-linealert-maintenance-view="'+esc(marker)+'" class="match-grid"><div><div class="eyebrow">POST-MAINTENANCE OBSERVATION · NORMAL INTERPRETATION PAUSED</div><h2>Watching the first production containers after maintenance</h2><p>'+esc(maintenance.workOrderId||'Maintenance')+' is complete. LineAlert is observing '+esc(maintenance.observedContainers||0)+' / '+esc(maintenance.targetContainers||10)+' synthetic healthy-reference containers before normal production interpretation resumes.</p><p><strong>No troubleshooting recommendation is active during this observation gate.</strong></p><p class="syncNote">Observation != return-to-service authorization, maintenance success, or safety approval.</p></div><div class="score"><div><span>ASSET</span><b>Labeler 2</b></div><div><span>STATE</span><b>Post-maintenance observe</b></div><div><span>OBSERVATION</span><b>'+esc(maintenance.observedContainers||0)+' / '+esc(maintenance.targetContainers||10)+'</b></div><div><span>NEXT</span><b>Resume normal interpretation after observation</b></div></div></div>';
  }

  store.subscribe(apply);
  const match=document.querySelector('.match');
  if(match){
    const observer=new MutationObserver(apply);
    observer.observe(match,{childList:true,subtree:true});
  }
  setInterval(apply,250);
  apply();
})();
