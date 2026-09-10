(function(global){
  'use strict';

  const STANDING_LABELS={
    most_supported:'Most supported',
    plausible:'Plausible',
    lower_priority:'Lower priority',
    less_supported:'Less supported',
    needs_more_evidence:'Needs more evidence'
  };

  function clone(value){return JSON.parse(JSON.stringify(value));}
  function finite(value){return Number.isFinite(value);}
  function lower(value){return String(value==null?'':value).toLowerCase();}

  function resolveIncidentId(session,events,requested){
    if(requested)return requested;
    if(session&&session.currentIncident&&session.currentIncident.id)return session.currentIncident.id;
    for(let i=(events||[]).length-1;i>=0;i--){
      const fields=events[i]&&events[i].fields||{};
      if(fields.incidentId)return fields.incidentId;
    }
    return null;
  }

  function eventsForIncident(events,incidentId){
    if(!incidentId)return [];
    return (events||[]).filter(event=>{
      const fields=event&&event.fields||{};
      return fields.incidentId===incidentId||fields.relatedIncidentId===incidentId;
    }).slice().sort((a,b)=>(a.seq||0)-(b.seq||0));
  }

  function mappedHypothesis(profile,actionKey,actionTitle){
    const title=lower(actionTitle);
    if(title.includes('roll loading')||title.includes('web path'))return 'roll_web_path';
    if(title.includes('guide')||title.includes('spacing')||title.includes('hold-down'))return 'guide_spacing';
    if(title.includes('timing')||title.includes('delay')||title.includes('speed'))return 'timing_controls';
    return profile&&profile.action_hypothesis_map?profile.action_hypothesis_map[actionKey]||null:null;
  }

  function setStanding(hypotheses,id,standing,note){
    const target=hypotheses.find(h=>h.id===id);
    if(!target)return;
    target.standing=standing;
    if(note){
      target.current_note=note;
      target.supports=target.supports||[];
      if(!target.supports.includes(note))target.supports.push(note);
    }
  }

  function initialHypotheses(profile,session){
    const hypotheses=clone(profile.working_hypotheses||[]).map(h=>Object.assign({},h,{standing:h.initial_standing||'needs_more_evidence'}));
    const title=session&&session.recommendationTitle||'';
    const weighted=mappedHypothesis(profile,session&&session.recommendation,title);
    if(weighted){
      hypotheses.forEach(h=>{
        if(h.id===weighted)h.standing='most_supported';
        else if(h.standing==='most_supported')h.standing='plausible';
      });
    }
    return hypotheses;
  }

  function currentHypotheses(profile,session,events){
    const hypotheses=initialHypotheses(profile,session||{});
    const latest=session&&session.latestTrial;
    const discipline=session&&session.discipline||{};
    const title=latest&&latest.actionTitle||session&&session.recommendationTitle||'';
    const tested=mappedHypothesis(profile,latest&&latest.actionKey||session&&session.lastAction,title);

    if(latest&&tested){
      const improved=finite(latest.beforeVar)&&finite(latest.afterVar)&&latest.afterVar<latest.beforeVar;
      if(improved){
        setStanding(
          hypotheses,
          tested,
          'most_supported',
          'The latest bounded run moved the observed presentation behavior toward the supplied healthy reference. That makes this explanation more useful for the next decision; it does not establish mechanism.'
        );
      }
    }

    const incidentEvents=eventsForIncident(events,session&&session.currentIncident&&session.currentIncident.id);
    const reviewed=[...incidentEvents].reverse().find(e=>e.eventClass==='FINDING'&&e.fields&&e.fields.recommendation);
    if(reviewed&&tested){
      if(reviewed.fields.recommendation==='restore_previous'){
        setStanding(
          hypotheses,
          tested,
          'less_supported',
          'The reviewed trial did not earn retention of this change. The path remains possible, but it is less useful for the next decision under the current evidence.'
        );
      }
      if(reviewed.fields.recommendation==='repeat'){
        setStanding(
          hypotheses,
          tested,
          'most_supported',
          'The first response was promising enough to justify a no-change repeat before another material change.'
        );
      }
    }

    if(session&&session.productionVerification&&tested){
      setStanding(
        hypotheses,
        tested,
        'most_supported',
        'The retained intervention is under production verification. Current operating response is consistent with this path, while causal certainty remains unclaimed.'
      );
    }

    if(session&&session.recoveryObserved&&tested){
      setStanding(
        hypotheses,
        tested,
        'most_supported',
        'Operating behavior remained stable through the configured verification window after the retained intervention.'
      );
    }

    if(discipline&&discipline.restoreContext&&tested){
      setStanding(
        hypotheses,
        tested,
        'less_supported',
        'The current trial workflow requires restoring the previous setting before another material change.'
      );
    }

    return hypotheses;
  }

  function disposition(profile,session){
    const table=profile.episode_dispositions||{};
    if(session&&session.recoveryObserved)return table.recovered||'Operating behavior stable under observed conditions';
    if(session&&session.productionVerification)return table.verification||'Operating response under bounded verification';
    if(session&&session.incident)return table.active||'Investigation active';
    return table.unresolved||'No active investigation';
  }

  function nextStep(profile,session){
    if(!session)return {action:'No active bounded step',why:'Open the Plant Canvas to establish a current synthetic episode.',authority:'No action requested'};
    if(session.recoveryObserved)return {
      action:'Resume normal monitoring',
      why:'The configured verification window completed with stable observed behavior.',
      authority:'Operational disposition only; no causal verdict is created.'
    };
    if(session.productionVerification)return {
      action:'Continue the bounded production verification window',
      why:'Do not introduce another material change while the retained intervention is being verified.',
      authority:'Follow the currently commissioned synthetic verification workflow.'
    };
    if(session.recommendationTitle)return {
      action:session.recommendationTitle,
      why:session.recommendationWhy||profile.next_step_principle,
      authority:'Recommendation only. Current action authority remains governed by the LineAlert action-authority profile.'
    };
    return {
      action:'Collect the next discriminating observation',
      why:profile.next_step_principle,
      authority:'Prefer observation before adjustment.'
    };
  }

  function snapshots(profile,session,events,incidentId){
    const relevant=eventsForIncident(events,incidentId);
    const incident=session&&session.currentIncident&&session.currentIncident.id===incidentId?session.currentIncident:null;
    const out=[];
    if(incident){
      out.push({
        key:'opened-'+incident.id,
        time:incident.time,
        type:'CONCERN',
        title:'Working investigation opened',
        detail:incident.summary||incident.title||'Current concern admitted for bounded investigation.',
        effect:'Multiple explanations remain in play; choose the next step for information value and operating risk.'
      });
    }
    relevant.forEach(event=>{
      const fields=event.fields||{};
      let effect='Evidence added to the episode record; reassess the next bounded decision.';
      if(event.eventClass==='ACTION')effect='A bounded intervention or change was recorded. Do not interpret the action itself as evidence that its underlying explanation is correct.';
      if(event.eventClass==='TRIAL')effect='A bounded test produced new observations. Use the result to change investigation priority, not to manufacture causal certainty.';
      if(event.eventClass==='FINDING'&&fields.recommendation==='repeat')effect='The observed response was promising enough to justify a no-change repeat before another material change.';
      if(event.eventClass==='FINDING'&&fields.recommendation==='restore_previous')effect='The tested path did not earn retention; restore the previous state before changing another variable.';
      if(event.eventClass==='RECOMMENDATION')effect='The next step changed because of the admitted evidence and trial discipline.';
      if(event.eventClass==='RECOVERY')effect='Operating behavior was stable through the configured verification conditions. The episode may close operationally without a terminal causal verdict.';
      out.push({
        key:event.eventId||('event-'+(event.seq||out.length)),
        time:event.time,
        type:event.eventClass||'EVIDENCE',
        title:event.message||event.eventClass||'Evidence update',
        detail:(event.source||'unknown source')+(fields.actionKey?' · action '+fields.actionKey:''),
        effect
      });
    });
    return out;
  }

  function derive(profile,session,events,requestedIncidentId){
    if(!profile||profile.classification!=='synthetic_demo_only')throw new Error('synthetic investigation profile required');
    const incidentId=resolveIncidentId(session,events,requestedIncidentId);
    const current=session&&(!incidentId||session.currentIncident&&session.currentIncident.id===incidentId)?session:null;
    return {
      schemaVersion:1,
      classification:'synthetic_demo_only',
      asset:profile.asset,
      episodeId:incidentId,
      disposition:disposition(profile,current),
      hypotheses:currentHypotheses(profile,current,events),
      nextStep:nextStep(profile,current),
      snapshots:snapshots(profile,current,events,incidentId),
      principles:{
        nextStep:profile.next_step_principle,
        boundaries:clone(profile.boundaries||[])
      }
    };
  }

  global.LineAlertInvestigationModel={
    STANDING_LABELS,
    derive,
    eventsForIncident,
    resolveIncidentId
  };
})(window);
