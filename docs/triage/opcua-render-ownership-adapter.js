(function(){
  'use strict';

  const browserUpdateModeLabels=updateModeLabels;

  function el(id){return document.getElementById(id);}

  function sourceStatus(){
    try{
      const source=window.LineAlertOpcuaSource;
      return source&&source.status?source.status():null;
    }catch(_){return null;}
  }

  function setText(id,text){
    const node=el(id);
    if(node)node.textContent=text;
  }

  function applyQualifiedMachineLabels(status){
    const runState=status.runStateCode;
    setText('fillerState','Context · no mapped OPC UA signal');
    setText('packerState','Context · no mapped OPC UA signal');
    setText('palletizerState','Context · no mapped OPC UA signal');
    setText(
      'nodeState',
      runState===0
        ?'Source reports stopped'
        :runState===2
          ?'Source reports diagnostic run'
          :'Source reports production'
    );
    setText(
      'modeTop',
      runState===0
        ?'LABELER 2 STOPPED · OPC UA CONNECTED'
        :runState===2
          ?'LABELER 2 DIAGNOSTIC RUN · OPC UA CONNECTED'
          :runState===1
            ?'LABELER 2 RUNNING · OPC UA CONNECTED'
            :'LABELER 2 STATE UNKNOWN · OPC UA CONNECTED'
    );
  }

  function applyPausedMachineLabels(status){
    setText('fillerState','Context · machine evidence paused');
    setText('packerState','Context · machine evidence paused');
    setText('palletizerState','Context · machine evidence paused');

    if(status.availabilityState==='connected_unqualified'){
      setText('nodeState','Evidence unqualified · last qualified state retained');
      setText('postureTop','EVIDENCE UNQUALIFIED · INTERPRETATION PAUSED');
      setText('modeTop','OPC UA CONNECTED · EVIDENCE UNQUALIFIED');
      return;
    }
    if(status.availabilityState==='disconnected'){
      setText('nodeState','Source disconnected · last observation stale');
      setText('postureTop','SOURCE DISCONNECTED · FAIL CLOSED');
      setText('modeTop','MACHINE INTERPRETATION PAUSED');
      return;
    }
    setText('nodeState','Bridge unavailable · source state unknown');
    setText('postureTop','BRIDGE UNAVAILABLE · FAIL CLOSED');
    setText('modeTop','MACHINE INTERPRETATION PAUSED');
  }

  updateModeLabels=function(){
    const result=browserUpdateModeLabels();
    const status=sourceStatus();
    if(!status||!status.everActivated)return result;
    if(status.availabilityState==='qualified')applyQualifiedMachineLabels(status);
    else applyPausedMachineLabels(status);
    return result;
  };
})();
