(function(){
  'use strict';
  const nav=document.querySelector('.nav');if(!nav||nav.querySelector('[data-linealert-event-log]'))return;
  const a=document.createElement('a');a.dataset.linealertEventLog='1';a.textContent='Event Log';
  a.href=location.pathname.includes('/triage/')?'../event-log.html':'./event-log.html';
  nav.appendChild(a);
})();
