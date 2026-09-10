(function(){
  'use strict';

  const store=window.LineAlertDemoSession;

  function current(){
    let direct=null;
    try{direct=typeof currentIncident!=='undefined'?currentIncident:null;}catch(_){direct=null;}
    if(direct)return direct;
    try{
      const saved=store?store.load():null;
      return saved&&saved.currentIncident?saved.currentIncident:null;
    }catch(_){return null;}
  }

  function ensure(){
    let row=document.getElementById('investigationLinkRow');
    if(row)return row;
    const why=document.getElementById('bestWhy');
    if(!why)return null;
    row=document.createElement('div');
    row.id='investigationLinkRow';
    row.style.cssText='margin:9px 0 2px;padding-top:9px;border-top:1px solid #dce3de';
    row.innerHTML='<a id="investigationLink" href="../investigation/" style="display:inline-block;font-size:.78rem;font-weight:900;color:#17211c;text-decoration:none">Open evolving investigation →</a><small style="display:block;margin-top:4px;color:#69756f;line-height:1.35">Working explanations · evidence for / against · next discriminating step · episode history</small>';
    why.insertAdjacentElement('afterend',row);
    return row;
  }

  function render(){
    const row=ensure();
    if(!row)return;
    const incident=current();
    let saved=null;
    try{saved=store?store.load():null;}catch(_){saved=null;}
    const hasEpisode=!!incident||!!(saved&&(saved.productionVerification||saved.recoveryObserved));
    if(!hasEpisode){row.style.display='none';return;}
    const id=incident&&incident.id||(saved&&saved.currentIncident&&saved.currentIncident.id)||'';
    const link=document.getElementById('investigationLink');
    link.href='../investigation/'+(id?'?incident='+encodeURIComponent(id):'');
    row.style.display='';
  }

  render();
  if(store)store.subscribe(render);
  setInterval(render,500);
})();
