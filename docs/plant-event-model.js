(function(){
  'use strict';
  const DAY=86400,H=3600;
  const CALENDAR_SEED='linealert-calendar-v1';
  const OPS_SEED='linealert-plant-ops-v1';
  const MAX_EVENTS=300;

  const incidentTypes={
    guide:{title:'Alignment variability emerging',summary:'Presentation variability crossed the synthetic concern threshold.',initialVar:21.6,quality:96.4,camera:'3 / 5 aligned',recommendation:'guide'},
    peel:{title:'Peel-edge instability emerging',summary:'Camera and presentation evidence show intermittent label release instability.',initialVar:18.9,quality:97.2,camera:'4 / 5 aligned',recommendation:'peel'},
    hold:{title:'Hold-down contact pattern drifting',summary:'Intermittent contact behavior coincides with elevated presentation variability.',initialVar:19.6,quality:96.9,camera:'3 / 5 aligned',recommendation:'hold'},
    speed:{title:'Rate-sensitive skew pattern emerging',summary:'Alignment consequence becomes more visible at the current production rate.',initialVar:17.9,quality:97.4,camera:'4 / 5 aligned',recommendation:'speed'}
  };

  const crew=[
    {id:'tech-a',name:'Tech A',skill:'Mechanical / packaging'},
    {id:'tech-b',name:'Tech B',skill:'Electrical / controls'}
  ];
  const jobTemplates=[
    {type:'PM',line:'Packaging Line 2',asset:'Capper 4',title:'Scheduled capper inspection',priority:'P3',skill:'mechanical'},
    {type:'Corrective',line:'Carton Line 1',asset:'Case Erector 3',title:'Intermittent blank-feed follow-up',priority:'P2',skill:'mechanical'},
    {type:'PM',line:'Packaging Line 1',asset:'Filler 1',title:'Lubrication / inspection route',priority:'P3',skill:'mechanical'},
    {type:'Corrective',line:'Packaging Line 2',asset:'Conveyor 6',title:'Photoeye nuisance-stop check',priority:'P2',skill:'controls'},
    {type:'Inspection',line:'Utilities',asset:'Air Header 1',title:'Pressure-drop verification',priority:'P3',skill:'controls'},
    {type:'Corrective',line:'Carton Line 1',asset:'Case Sealer 2',title:'Tape-head tracking complaint',priority:'P2',skill:'mechanical'}
  ];

  function dayStart(abs){return Math.floor(abs/DAY)*DAY;}
  function secOfDay(abs){return ((abs%DAY)+DAY)%DAY;}
  function dateKey(abs){return new Date(dayStart(abs)*1000).toISOString().slice(0,10);}
  function displayDate(abs){return new Date(dayStart(abs)*1000).toLocaleDateString(undefined,{weekday:'short',year:'numeric',month:'short',day:'numeric',timeZone:'UTC'});}
  function fmt(abs,seconds=true){const s=secOfDay(abs),h=Math.floor(s/H),m=Math.floor((s%H)/60),x=Math.floor(s%60);return String(h).padStart(2,'0')+':'+String(m).padStart(2,'0')+(seconds?':'+String(x).padStart(2,'0'):'');}
  function hash32(s){let h=2166136261;for(let i=0;i<s.length;i++){h^=s.charCodeAt(i);h=Math.imul(h,16777619);}return h>>>0;}
  function shiftAt(abs){const d=dayStart(abs),s=secOfDay(abs);if(s<6*H)return{code:'N',name:'NIGHT SHIFT',start:d-2*H,end:d+6*H,hard:d+5.5*H,shiftDate:dateKey(d-DAY)};if(s<14*H)return{code:'D',name:'DAY SHIFT',start:d+6*H,end:d+14*H,hard:d+13.75*H,shiftDate:dateKey(d)};if(s<22*H)return{code:'E',name:'EVENING SHIFT',start:d+14*H,end:d+22*H,hard:d+21.5*H,shiftDate:dateKey(d)};return{code:'N',name:'NIGHT SHIFT',start:d+22*H,end:d+30*H,hard:d+29.5*H,shiftDate:dateKey(d)};}
  function nextShift(s){return shiftAt(s.end+1);}
  function shiftEvent(shift){const base=CALENDAR_SEED+'|'+shift.shiftDate+'|'+shift.code,roll=hash32(base)%100;if(roll<80)return null;const kind=roll<90?'guide':roll<95?'peel':roll<98?'hold':'speed';const earliest=shift.start+45*60,latest=shift.hard-45*60,span=Math.max(1,Math.floor(latest-earliest)),time=earliest+(hash32(base+'|time')%span),type=incidentTypes[kind];return{id:'INC-'+shift.shiftDate.replaceAll('-','')+'-'+shift.code+'-01',shift,kind,time,title:type.title,summary:type.summary,initialVar:type.initialVar,quality:type.quality,camera:type.camera,recommendation:type.recommendation};}
  function shiftJobs(shift){const base=OPS_SEED+'|'+shift.shiftDate+'|'+shift.code;const count=3+(hash32(base+'|count')%3),jobs=[];for(let i=0;i<count;i++){const t=jobTemplates[hash32(base+'|template|'+i)%jobTemplates.length];const arrivalOffset=(25+hash32(base+'|arrival|'+i)%330)*60;const duration=(22+hash32(base+'|duration|'+i)%54)*60;const arrival=Math.min(shift.hard-20*60,shift.start+arrivalOffset);jobs.push({id:'WO-'+shift.shiftDate.replaceAll('-','')+'-'+shift.code+'-'+String(i+1).padStart(2,'0'),...t,arrival,duration});}return jobs.sort((a,b)=>a.arrival-b.arrival);}
  function jobPlan(shift){const techFree=[shift.start,shift.start],plans=[];for(const j of shiftJobs(shift)){const compatible=j.skill==='controls'?[1,0]:[0,1];let ti=compatible[0];if(techFree[compatible[1]]<techFree[ti])ti=compatible[1];const start=Math.max(j.arrival,techFree[ti]),end=start+j.duration;techFree[ti]=end;plans.push({...j,techIndex:ti,start,end});}return plans;}

  function makeEvent(time,source,eventClass,severity,asset,message,fields={}){
    const seed=[time,source,eventClass,asset,message].join('|');
    return{
      eventId:'EVT-'+dateKey(time).replaceAll('-','')+'-'+fmt(time,false).replace(':','')+'-'+String(hash32(seed)%10000).padStart(4,'0'),
      time,source,eventClass,severity,asset,message,
      clockQuality:'synthetic_calendar_clock',
      classification:'synthetic_demo_only',
      fields
    };
  }
  function scheduleEventsForDay(d){
    return[
      makeEvent(d+5.5*H,'synthetic-mes/packaging-line-1','SCHEDULE','Information','Packaging Line 1','Night sanitation window started',{runState:'scheduled sanitation'}),
      makeEvent(d+6*H,'synthetic-mes/packaging-line-1','PRODUCTION','Information','Packaging Line 1','Day production window started',{runState:'production'}),
      makeEvent(d+13.75*H,'synthetic-mes/packaging-line-1','CHANGEOVER','Information','Packaging Line 1','Day-to-evening changeover window started',{planned:true}),
      makeEvent(d+14*H,'synthetic-mes/packaging-line-1','PRODUCTION','Information','Packaging Line 1','Evening production window started',{runState:'production'}),
      makeEvent(d+21.5*H,'synthetic-mes/packaging-line-1','CHANGEOVER','Information','Packaging Line 1','Evening-to-night changeover window started',{planned:true}),
      makeEvent(d+22*H,'synthetic-mes/packaging-line-1','PRODUCTION','Information','Packaging Line 1','Night production window started',{runState:'production'})
    ];
  }
  function workEventsForShift(shift){
    const events=[];
    for(const job of jobPlan(shift)){
      const tech=crew[job.techIndex];
      events.push(makeEvent(job.arrival,'synthetic-cmms/plant','WORK_ORDER','Information',job.asset,job.id+' received · '+job.title,{workOrderId:job.id,line:job.line,priority:job.priority,type:job.type,status:'received'}));
      events.push(makeEvent(job.start,'synthetic-maintenance/dispatch','MAINTENANCE','Information',job.asset,tech.name+' started '+job.id,{workOrderId:job.id,technician:tech.name,line:job.line,status:'in_progress'}));
      events.push(makeEvent(job.end,'synthetic-maintenance/dispatch','MAINTENANCE','Information',job.asset,tech.name+' completed '+job.id,{workOrderId:job.id,technician:tech.name,line:job.line,status:'completed'}));
    }
    return events;
  }
  function incidentEventsForShift(shift){
    const inc=shiftEvent(shift);if(!inc)return[];
    const events=[];
    if(inc.kind==='guide'){
      const lead=(9+(hash32(inc.id+'|roll-lead')%10))*60;
      const rollTime=Math.max(shift.start+8*60,inc.time-lead);
      const pauseTime=Math.max(shift.start+5*60,rollTime-2*60);
      const restartTime=Math.min(inc.time-3*60,rollTime+3*60);
      const change=makeEvent(rollTime,'synthetic-operator/changeover','CHANGEOVER','Information','Labeler 2','Label roll replaced and changeover record completed',{operator:'Shift operator',changeType:'label_roll_replacement',setupReference:'Approved marked setup reference',relatedIncidentId:inc.id,boundary:'preceded_by_change_does_not_establish_cause'});
      events.push(makeEvent(pauseTime,'synthetic-hmi/packaging-line-1','PRODUCTION','Information','Packaging Line 1','Production paused for label roll change',{runState:'stopped_changeover',relatedIncidentId:inc.id}));
      events.push(change);
      events.push(makeEvent(restartTime,'synthetic-hmi/packaging-line-1','PRODUCTION','Information','Packaging Line 1','Production resumed after recorded roll change',{runState:'production',relatedIncidentId:inc.id}));
    }
    events.push(makeEvent(Math.max(shift.start,inc.time-120),'synthetic-telemetry/labeler2','TELEMETRY','Notice','Labeler 2','Presentation variability moved outside matched healthy behavior',{relatedIncidentId:inc.id,signal:'presentation_interval_stddev_ms',valueMs:inc.initialVar}));
    events.push(makeEvent(inc.time,'linealert/deterministic','CONCERN','Attention','Labeler 2',inc.title+' · concern threshold crossed',{incidentId:inc.id,incidentKind:inc.kind,boundary:'telemetry_threshold_crossing_is_evidence_not_diagnosis'}));
    return events;
  }
  function precedingContext(incident){
    if(!incident||incident.kind!=='guide'||!Number.isFinite(incident.time))return null;
    const shift=incident.shift||shiftAt(incident.time);
    const events=incidentEventsForShift(shift).filter(e=>e.time<incident.time&&e.eventClass==='CHANGEOVER'&&e.asset==='Labeler 2');
    return events.sort((a,b)=>b.time-a.time)[0]||null;
  }
  function generatedEvents(asOf,lookbackSeconds=24*H,lookaheadSeconds=0){
    const start=asOf-lookbackSeconds,end=asOf+lookaheadSeconds,events=[];
    const firstDay=dayStart(start)-DAY,lastDay=dayStart(end)+DAY;
    for(let d=firstDay;d<=lastDay;d+=DAY){events.push(...scheduleEventsForDay(d));}
    let s=shiftAt(start-DAY);const seen=new Set();
    for(let i=0;i<20&&s.start<=end+DAY;i++,s=nextShift(s)){
      const key=s.shiftDate+'|'+s.code;if(seen.has(key))continue;seen.add(key);
      events.push(...workEventsForShift(s),...incidentEventsForShift(s));
    }
    return events.filter(e=>e.time>=start&&e.time<=end).sort((a,b)=>b.time-a.time).slice(0,MAX_EVENTS);
  }

  window.LineAlertPlantEventModel={DAY,H,CALENDAR_SEED,OPS_SEED,incidentTypes,hash32,dayStart,dateKey,displayDate,fmt,shiftAt,nextShift,shiftEvent,shiftJobs,jobPlan,generatedEvents,precedingContext,makeEvent};
})();
