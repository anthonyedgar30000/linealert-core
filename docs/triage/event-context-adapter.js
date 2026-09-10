(function(){
  'use strict';
  const model=window.LineAlertPlantEventModel;
  if(!model)return;

  function normalizeIncidentVocabulary(){
    try{
      if(typeof incidentTypes!=='undefined'&&incidentTypes.guide){
        incidentTypes.guide.title='Alignment variability emerging';
        incidentTypes.guide.summary='Presentation variability has crossed the synthetic concern threshold.';
      }
      if(typeof currentIncident!=='undefined'&&currentIncident&&currentIncident.kind==='guide'){
        currentIncident.title='Alignment variability emerging';
        currentIncident.summary='Presentation variability has crossed the synthetic concern threshold.';
      }
      if(typeof fastEvent!=='undefined'&&fastEvent&&fastEvent.kind==='guide'){
        fastEvent.title='Alignment variability emerging';
        fastEvent.summary='Presentation variability has crossed the synthetic concern threshold.';
      }
      const headline=document.getElementById('assetHeadline');
      const summary=document.getElementById('assetSummary');
      if(typeof currentIncident!=='undefined'&&currentIncident&&currentIncident.kind==='guide'){
        if(headline)headline.textContent=currentIncident.title;
        if(summary)summary.textContent=currentIncident.summary;
      }
      const history=document.getElementById('history');
      if(history&&history.innerHTML.includes('Alignment variability after roll change'))history.innerHTML=history.innerHTML.replaceAll('Alignment variability after roll change','Alignment variability emerging');
    }catch(_){}
  }

  function ensureCard(){
    let card=document.getElementById('recentRecordedContext');
    if(card)return card;
    const summary=document.getElementById('assetSummary');if(!summary)return null;
    card=document.createElement('div');card.id='recentRecordedContext';card.className='hidden';
    card.style.cssText='margin:10px 0 12px;padding:11px 12px;border:1px solid #d8dfda;border-radius:12px;background:#f8faf8';
    card.innerHTML='<span style="display:block;font-size:.6rem;font-weight:900;letter-spacing:.1em;color:#69756f">RECENT RECORDED CONTEXT</span><b id="recentContextTitle" style="display:block;margin:5px 0 3px"></b><small id="recentContextMeta" style="display:block;color:#69756f;line-height:1.35"></small><a id="recentContextLink" href="../event-log.html" style="display:inline-block;margin-top:7px;font-size:.72rem;font-weight:850;color:#17211c">Open in Event Log →</a>';
    summary.insertAdjacentElement('afterend',card);return card;
  }
  function renderContext(){
    normalizeIncidentVocabulary();
    const card=ensureCard();if(!card)return;
    let inc=null;try{inc=typeof currentIncident!=='undefined'?currentIncident:null;}catch(_){}
    if(!inc||inc.kind!=='guide'||!Number.isFinite(inc.time)){card.classList.add('hidden');return;}
    const evt=model.precedingContext(inc);if(!evt){card.classList.add('hidden');return;}
    const delta=Math.max(0,Math.round((inc.time-evt.time)/60));
    document.getElementById('recentContextTitle').textContent=model.fmt(evt.time,false)+' · '+evt.message;
    document.getElementById('recentContextMeta').textContent=evt.source+' · '+evt.eventId+' · '+delta+' min before concern · preceded by change ≠ caused by change';
    document.getElementById('recentContextLink').href='../event-log.html?incident='+encodeURIComponent(inc.id);
    card.classList.remove('hidden');
  }

  normalizeIncidentVocabulary();
  try{if(typeof renderTicketHistory==='function')renderTicketHistory();}catch(_){}
  renderContext();
  setInterval(renderContext,500);
})();
