(function(){
  'use strict';

  const store=window.LineAlertDemoSession;
  let priorBodyOverflow='';

  function current(){
    let direct=null;
    try{direct=typeof currentIncident!=='undefined'?currentIncident:null;}catch(_){direct=null;}
    if(direct)return direct;
    try{
      const saved=store?store.load():null;
      return saved&&saved.currentIncident?saved.currentIncident:null;
    }catch(_){return null;}
  }

  function investigationHref(id){
    return '../investigation/'+(id?'?incident='+encodeURIComponent(id):'');
  }

  function ensureDrawer(){
    let backdrop=document.getElementById('investigationDrawerBackdrop');
    if(backdrop)return backdrop;

    const style=document.createElement('style');
    style.id='investigationDrawerStyle';
    style.textContent='\n'+
      '#investigationDrawerBackdrop{position:fixed;inset:0;z-index:10000;background:rgba(20,29,24,.38);display:none;justify-content:flex-end}\n'+
      '#investigationDrawerBackdrop.open{display:flex}\n'+
      '#investigationDrawer{width:min(760px,94vw);height:100%;background:#eef1ed;border-left:1px solid #c8d1cb;box-shadow:-18px 0 45px rgba(23,33,28,.16);display:flex;flex-direction:column}\n'+
      '#investigationDrawerHeader{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:12px 14px;background:#fff;border-bottom:1px solid #d5dbd7}\n'+
      '#investigationDrawerHeader b{display:block;font-size:.92rem}\n'+
      '#investigationDrawerHeader small{display:block;margin-top:2px;color:#69756f;font-size:.7rem}\n'+
      '#investigationDrawerActions{display:flex;gap:7px;align-items:center;white-space:nowrap}\n'+
      '#investigationDrawerActions a,#investigationDrawerActions button{appearance:none;border:1px solid #cbd3ce;border-radius:999px;background:#fff;color:#17211c;padding:7px 10px;font:800 .72rem Inter,system-ui,sans-serif;text-decoration:none;cursor:pointer}\n'+
      '#investigationFrame{width:100%;flex:1;border:0;background:#eef1ed}\n'+
      '@media(max-width:680px){#investigationDrawer{width:100vw}#investigationDrawerHeader{align-items:flex-start}#investigationDrawerHeader small{max-width:190px}}';
    document.head.appendChild(style);

    backdrop=document.createElement('div');
    backdrop.id='investigationDrawerBackdrop';
    backdrop.setAttribute('aria-hidden','true');
    backdrop.innerHTML='\n'+
      '<section id="investigationDrawer" role="dialog" aria-modal="true" aria-labelledby="investigationDrawerTitle">\n'+
      '  <div id="investigationDrawerHeader">\n'+
      '    <div><b id="investigationDrawerTitle">Evolving investigation</b><small>Same synthetic episode · Plant Canvas continues running underneath.</small></div>\n'+
      '    <div id="investigationDrawerActions"><a id="investigationFullPage" href="../investigation/" target="_blank" rel="noopener">Full page ↗</a><button id="investigationClose" type="button">Close</button></div>\n'+
      '  </div>\n'+
      '  <iframe id="investigationFrame" title="Evolving investigation workspace"></iframe>\n'+
      '</section>';
    document.body.appendChild(backdrop);

    document.getElementById('investigationClose').addEventListener('click',closeDrawer);
    backdrop.addEventListener('click',function(ev){if(ev.target===backdrop)closeDrawer();});
    document.addEventListener('keydown',function(ev){if(ev.key==='Escape'&&backdrop.classList.contains('open'))closeDrawer();});
    return backdrop;
  }

  function openDrawer(id){
    const backdrop=ensureDrawer();
    const href=investigationHref(id);
    const frame=document.getElementById('investigationFrame');
    const full=document.getElementById('investigationFullPage');
    if(frame.getAttribute('src')!==href)frame.setAttribute('src',href);
    full.href=href;
    backdrop.classList.add('open');
    backdrop.setAttribute('aria-hidden','false');
    priorBodyOverflow=document.body.style.overflow;
    document.body.style.overflow='hidden';
    const link=document.getElementById('investigationLink');
    if(link)link.setAttribute('aria-expanded','true');
    document.getElementById('investigationClose').focus();
  }

  function closeDrawer(){
    const backdrop=document.getElementById('investigationDrawerBackdrop');
    if(!backdrop)return;
    backdrop.classList.remove('open');
    backdrop.setAttribute('aria-hidden','true');
    document.body.style.overflow=priorBodyOverflow;
    const link=document.getElementById('investigationLink');
    if(link){link.setAttribute('aria-expanded','false');link.focus();}
  }

  function ensure(){
    let row=document.getElementById('investigationLinkRow');
    if(row)return row;
    const why=document.getElementById('bestWhy');
    if(!why)return null;
    row=document.createElement('div');
    row.id='investigationLinkRow';
    row.style.cssText='margin:9px 0 2px;padding-top:9px;border-top:1px solid #dce3de';
    row.innerHTML='<a id="investigationLink" href="../investigation/" aria-haspopup="dialog" aria-expanded="false" style="display:inline-block;font-size:.78rem;font-weight:900;color:#17211c;text-decoration:none">Open evolving investigation →</a><small style="display:block;margin-top:4px;color:#69756f;line-height:1.35">Opens over the live Canvas · working explanations · evidence for / against · next discriminating step · episode history</small>';
    why.insertAdjacentElement('afterend',row);
    const link=document.getElementById('investigationLink');
    link.addEventListener('click',function(ev){
      const incident=current();
      let saved=null;
      try{saved=store?store.load():null;}catch(_){saved=null;}
      const id=incident&&incident.id||(saved&&saved.currentIncident&&saved.currentIncident.id)||'';
      ev.preventDefault();
      openDrawer(id);
    });
    return row;
  }

  function render(){
    const row=ensure();
    if(!row)return;
    const incident=current();
    let saved=null;
    try{saved=store?store.load():null;}catch(_){saved=null;}
    const hasEpisode=!!incident||!!(saved&&(saved.productionVerification||saved.recoveryObserved));
    if(!hasEpisode){
      row.style.display='none';
      closeDrawer();
      return;
    }
    const id=incident&&incident.id||(saved&&saved.currentIncident&&saved.currentIncident.id)||'';
    const href=investigationHref(id);
    const link=document.getElementById('investigationLink');
    link.href=href;
    row.style.display='';

    const backdrop=document.getElementById('investigationDrawerBackdrop');
    if(backdrop&&backdrop.classList.contains('open')){
      const frame=document.getElementById('investigationFrame');
      const full=document.getElementById('investigationFullPage');
      if(frame.getAttribute('src')!==href)frame.setAttribute('src',href);
      full.href=href;
    }
  }

  render();
  if(store)store.subscribe(render);
  setInterval(render,500);
})();
