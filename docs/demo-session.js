(function(global){
  'use strict';
  const KEY='linealert.synthetic.demo-session.v1';
  const CHANNEL='linealert-synthetic-demo-session-v1';
  const VERSION=1;
  let channel=null;
  try{if('BroadcastChannel' in global)channel=new BroadcastChannel(CHANNEL)}catch(_){channel=null}

  function valid(value){
    return !!value&&value.schemaVersion===VERSION&&value.classification==='synthetic_demo_only';
  }
  function load(){
    try{
      const raw=global.localStorage&&global.localStorage.getItem(KEY);
      if(!raw)return null;
      const parsed=JSON.parse(raw);
      return valid(parsed)?parsed:null;
    }catch(_){return null}
  }
  function save(snapshot){
    if(!snapshot||typeof snapshot!=='object')return null;
    const value=Object.assign({},snapshot,{
      schemaVersion:VERSION,
      classification:'synthetic_demo_only',
      updatedAtMs:Date.now()
    });
    try{global.localStorage&&global.localStorage.setItem(KEY,JSON.stringify(value))}catch(_){/* demo remains usable without storage */}
    try{channel&&channel.postMessage(value)}catch(_){/* cross-tab sync is best effort */}
    return value;
  }
  function clear(){
    try{global.localStorage&&global.localStorage.removeItem(KEY)}catch(_){}
    try{channel&&channel.postMessage({schemaVersion:VERSION,classification:'synthetic_demo_only',cleared:true,updatedAtMs:Date.now()})}catch(_){}
  }
  function subscribe(fn){
    if(typeof fn!=='function')return function(){};
    const onStorage=function(e){
      if(e.key!==KEY)return;
      if(!e.newValue){fn(null);return}
      try{const parsed=JSON.parse(e.newValue);if(valid(parsed))fn(parsed)}catch(_){}
    };
    global.addEventListener('storage',onStorage);
    const onMessage=function(e){if(valid(e.data))fn(e.data);else if(e.data&&e.data.cleared)fn(null)};
    if(channel)channel.addEventListener('message',onMessage);
    return function(){
      global.removeEventListener('storage',onStorage);
      if(channel)channel.removeEventListener('message',onMessage);
    };
  }
  global.LineAlertDemoSession={KEY,VERSION,load,save,clear,subscribe};
})(window);
