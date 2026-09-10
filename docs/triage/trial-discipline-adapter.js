(function(){
  'use strict';

  const MATERIAL_ACTIONS=new Set(['guide','peel','hold','delay','speed']);
  const SETTING_NAMES={guide:'guide / spacing',peel:'peel angle',hold:'hold-down',delay:'label delay',speed:'line speed'};
  const state={completedTrials:0,pendingExperimental:null,restoreContext:null,retained:[],activeTrial:null};

  const baseResetWorkflowForIncident=resetWorkflowForIncident;
  const baseRenderHero=renderHero;

  function clone(value){return value==null?value:JSON.parse(JSON.stringify(value));}
  function captureEvidence(){return{v:currentVar,camera:q('cameraVal').textContent,quality:q('qualityVal').textContent};}
  function acceptedFrom(text){
    const value=String(text||'');
    const match=value.match(/([0-5])\s*\/\s*5/);
    if(match)return match[1]+' / 5 accepted';
    const pct=parseFloat(value);
    if(Number.isFinite(pct))return pct>=98.5?'5 / 5 accepted':pct>=97?'4 / 5 accepted':'3 / 5 accepted';
    return '3 / 5 accepted';
  }
  function alignedFrom(text,v){
    const value=String(text||'');
    const match=value.match(/([0-5])\s*\/\s*5/);
    if(match)return match[1]+' / 5 aligned';
    return v<=VERIFY_VAR_MAX?'5 / 5 aligned':v<19.5?'4 / 5 aligned':'3 / 5 aligned';
  }
  function skewFrom(aligned){const n=parseInt(aligned,10);return String(Math.max(0,5-(Number.isFinite(n)?n:3)));}
  function outcomeVerdict(actionKey,before,out){
    if(actionKey==='repeat')return 'verification';
    if(actionKey==='speed')return 'diagnostic_only';
    const healthy=out.v<=VERIFY_VAR_MAX&&out.aligned.startsWith('5 / 5')&&out.accepted.startsWith('5 / 5');
    if(healthy)return 'strong';
    if(out.v>before+.4)return 'adverse';
    if((before-out.v)<1)return 'no_useful';
    return 'partial';
  }
  function prepareRestoreAction(){
    const ctx=state.restoreContext;
    if(!ctx)return;
    const name=SETTING_NAMES[ctx.actionKey]||'last changed setting';
    const aligned=alignedFrom(ctx.pre.camera,ctx.pre.v);
    actions.restore_previous={
      title:'Restore '+name+' to previous approved setting',
      why:'The last bounded trial did not earn retention. Restore the one changed setting before introducing another material change.',
      out:{
        v:ctx.pre.v,
        aligned,
        accepted:acceptedFrom(ctx.pre.quality),
        skew:skewFrom(aligned),
        text:'Previous setting restored; fresh verification returned near the pre-change evidence state.',
        next:ctx.nextRecommendation||'guide'
      }
    };
  }
  function gate(actionKey){
    if(trialInProgress)return{allowed:false,reason:'A trial is already armed. Complete or review that trial before another action.'};
    if(actionKey==='restore_previous')return{allowed:!!state.restoreContext,reason:'No explicit restore is currently required.'};
    if(state.restoreContext&&MATERIAL_ACTIONS.has(actionKey))return{allowed:false,reason:'Restore the previous unhelpful change and verify that restore before another material change.'};
    if(state.pendingExperimental&&MATERIAL_ACTIONS.has(actionKey))return{allowed:false,reason:'The current improvement has not earned retention yet. Repeat with no further change before stacking another material change.'};
    return{allowed:true,reason:''};
  }
  function resetDiscipline(){
    state.completedTrials=0;state.pendingExperimental=null;state.restoreContext=null;state.retained=[];state.activeTrial=null;
    iteration=0;
    if(actions.restore_previous)delete actions.restore_previous;
  }
  function retentionNote(){
    if(state.restoreContext)return 'Single-change discipline: the previous setting must be explicitly restored and verified before another material change.';
    if(state.pendingExperimental)return 'Single-change discipline: this improvement is still experimental. Repeat it without another material change before it can be retained.';
    if(state.retained.length)return 'Verified intermediate state retained: '+state.retained.map(x=>x.title).join(' + ')+'. A later additional change may now be tested one at a time.';
    return 'Single-change discipline: only one material difference is introduced from the last verified state.';
  }

  resetWorkflowForIncident=function(e){resetDiscipline();baseResetWorkflowForIncident(e);};

  renderHero=function(){
    baseRenderHero();
    if(!incident||productionVerification||recoveryObserved)return;
    if(state.restoreContext){
      q('bestWhy').textContent='The last trial did not earn retention. Restore only the '+(SETTING_NAMES[state.restoreContext.actionKey]||'changed setting')+' to its previous approved setting, then run a fresh 5-container verification before another material change. Recommendation is advisory, not authorization or an equipment command.';
      q('nextBtn').textContent='Restore previous setting → arm 5-container verification';
    }else if(state.pendingExperimental&&recommendation==='repeat'){
      q('bestWhy').textContent='The current change produced a strong improvement, but stacking has not been earned yet. Repeat with no further material change. If the improvement reproduces, this configuration becomes a verified intermediate state.';
    }else if(q('bestWhy')&&q('bestWhy').textContent){
      q('bestWhy').textContent+=' '+retentionNote();
    }
    if(trialInProgress){q('nextBtn').disabled=true;q('nextBtn').textContent='Trial already armed · complete HMI run';}
  };

  renderActions=function(){
    const entries=Object.entries(actions).filter(([k])=>k!==recommendation&&(k!=='restore_previous'||!!state.restoreContext));
    q('actionList').innerHTML=entries.map(([k,a])=>{
      const g=gate(k),note=!g.allowed?' · WAIT: '+g.reason:'';
      return '<div class="action" data-key="'+k+'"><strong>'+a.title+'</strong><small>'+a.why+note+'</small></div>';
    }).join('');
    document.querySelectorAll('.action').forEach(el=>el.onclick=()=>choose(el.dataset.key));
    renderHero();
  };

  choose=function(k){
    if(!actions[k])return;
    const g=gate(k);
    document.querySelectorAll('.action').forEach(x=>x.classList.toggle('selected',g.allowed&&x.dataset.key===k));
    if(!g.allowed){
      q('selectedTitle').textContent='Not available yet: '+actions[k].title;
      q('selectedWhy').textContent=g.reason;
      q('armBtn').disabled=true;
      show('selectionBox');
      return;
    }
    selectedAction=k;
    q('selectedTitle').textContent='Selected: '+actions[k].title;
    q('selectedWhy').textContent=actions[k].why+' '+retentionNote();
    q('armBtn').disabled=false;
    show('selectionBox');
  };

  armTrial=function(k){
    if(mode!=='diagnostic'||!k||!actions[k])return;
    const g=gate(k);
    if(!g.allowed){
      q('selectedTitle').textContent='Action held: '+actions[k].title;
      q('selectedWhy').textContent=g.reason;
      q('armBtn').disabled=true;
      show('selectionBox');
      return;
    }
    selectedAction=k;lastAction=k;trialBeforeVar=currentVar;trialInProgress=true;
    state.activeTrial={actionKey:k,pre:captureEvidence(),trialNumber:state.completedTrials+1};
    q('trialState').textContent='TRIAL ARMED · WAITING FOR HMI';
    q('trialAction').textContent=actions[lastAction].title;
    show('trialSection');show('trialResult',false);show('confirmBtn',false);
    q('hmiBtn').disabled=false;q('hmiBtn').textContent='Demo · HMI executes 5-container run';
    q('armBtn').disabled=true;
    renderHero();
  };

  q('confirmBtn').onclick=()=>{
    if(!lastAction||!actions[lastAction]||!trialInProgress)return;
    const o=actions[lastAction].out;
    state.completedTrials++;
    iteration=state.completedTrials;
    showLastTrial(lastAction,trialBeforeVar,o);
    const h=document.createElement('div');
    h.innerHTML='<b>Trial '+iteration+' · '+actions[lastAction].title+'</b><small>'+o.accepted+' · '+o.aligned+' · '+trialBeforeVar.toFixed(1)+' → '+o.v.toFixed(1)+' ms SD. '+o.text+'</small>';
    q('history').appendChild(h);
    show('trialSection',false);show('selectionBox',false);trialInProgress=false;lastConfirmedTrial=true;q('armBtn').disabled=false;

    if(lastAction==='restore_previous'){
      const ctx=state.restoreContext;
      const r=document.createElement('div');
      r.innerHTML='<b>Previous setting restored and verified</b><small>The prior '+(ctx?(SETTING_NAMES[ctx.actionKey]||'changed setting'):'setting')+' was explicitly restored. Fresh evidence returned near the pre-change state. No automatic equipment reset occurred.</small>';
      q('history').appendChild(r);
      recommendation=ctx&&ctx.nextRecommendation?ctx.nextRecommendation:(o.next||'guide');
      selectedAction=recommendation;nextStage='action';state.restoreContext=null;state.pendingExperimental=null;state.activeTrial=null;
    }else if(lastAction==='repeat'){
      if(state.pendingExperimental){
        const retained={actionKey:state.pendingExperimental.actionKey,title:state.pendingExperimental.title,verifiedAtTrial:iteration};
        if(!state.retained.some(x=>x.actionKey===retained.actionKey))state.retained.push(retained);
        const r=document.createElement('div');
        r.innerHTML='<b>Verified intermediate state retained</b><small>'+retained.title+' reproduced without another material change. Stacking is now earned from this verified state; any next trial may introduce only one additional material difference.</small>';
        q('history').appendChild(r);
        state.pendingExperimental=null;
      }
      if(o.next==='production'){nextStage='production_verification';recommendation=null;}else{recommendation=o.next;nextStage='action';selectedAction=recommendation;}
      state.activeTrial=null;
    }else{
      const verdict=outcomeVerdict(lastAction,trialBeforeVar,o);
      if(verdict==='strong'){
        state.pendingExperimental={actionKey:lastAction,title:actions[lastAction].title,pre:clone(state.activeTrial&&state.activeTrial.pre),result:{v:o.v,aligned:o.aligned,accepted:o.accepted}};
        recommendation='repeat';selectedAction='repeat';nextStage='action';
      }else{
        state.restoreContext={actionKey:lastAction,title:actions[lastAction].title,pre:clone(state.activeTrial&&state.activeTrial.pre)||{v:trialBeforeVar,camera:'',quality:''},nextRecommendation:o.next||'guide',verdict};
        prepareRestoreAction();recommendation='restore_previous';selectedAction='restore_previous';nextStage='restore_required';
        const r=document.createElement('div');
        r.innerHTML='<b>Restore required before another material change</b><small>The '+(SETTING_NAMES[lastAction]||'changed setting')+' trial did not earn retention ('+verdict.replaceAll('_',' ')+'). LineAlert recommends explicitly restoring that one setting and verifying the restore before testing another material change.</small>';
        q('history').appendChild(r);
      }
      state.activeTrial=null;
    }
    renderActions();
  };

  window.LineAlertTrialDiscipline={
    snapshot(){return clone(state);},
    restore(saved){
      if(!saved)return;
      state.completedTrials=Number.isFinite(saved.completedTrials)?saved.completedTrials:(Number.isFinite(iteration)?iteration:0);
      state.pendingExperimental=clone(saved.pendingExperimental)||null;
      state.restoreContext=clone(saved.restoreContext)||null;
      state.retained=Array.isArray(saved.retained)?clone(saved.retained):[];
      state.activeTrial=clone(saved.activeTrial)||null;
      iteration=state.completedTrials;
      if(state.restoreContext)prepareRestoreAction();
      renderActions();
    },
    reset:resetDiscipline,
    status(){return clone(state);}
  };

  renderActions();
})();
