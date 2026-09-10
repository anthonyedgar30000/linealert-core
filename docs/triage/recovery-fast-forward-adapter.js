(function(){
  'use strict';

  const button=document.getElementById('speedBtn');
  if(!button||typeof completeRecovery!=='function'||typeof updateSpeedControl!=='function')return;

  const baseCompleteRecovery=completeRecovery;
  const baseSpeedClick=button.onclick;

  function clearFastForwardState(){
    fast=false;
    fastTarget=null;
    fastEvent=null;
  }

  function leaveRecoveredEpisodeForAdvance(){
    if(!(recoveryObserved&&!incident&&!productionVerification&&mode==='production'))return false;

    // Recovery is already recorded in the handled-incident/history evidence. Moving on
    // should clear only the live episode projection, not erase that chronology.
    recoveryObserved=false;
    currentIncident=null;
    recommendation=null;
    nextStage='action';
    trialInProgress=false;

    show('verificationCard',false);
    show('trialSection',false);
    show('selectionBox',false);
    q('watchPill').textContent='Normal';
    q('concernCount').textContent='0';
    q('labelerNode').classList.remove('watch');
    selectAsset('filler');
    updateModeLabels();
    schedule();
    renderTicketHistory();
    renderOps();
    return true;
  }

  completeRecovery=function(){
    // A completed verification must not inherit the target/event from the fast-forward
    // that originally delivered this incident. The next advance starts from current time.
    clearFastForwardState();
    baseCompleteRecovery();
    clearFastForwardState();
    updateSpeedControl();
  };

  button.onclick=function(){
    if(incident||mode==='diagnostic'||productionVerification)return;

    // Once the user asks to move to the next incident, the just-closed episode becomes
    // history and the canvas returns to normal monitoring before choosing a new target.
    leaveRecoveredEpisodeForAdvance();
    clearFastForwardState();
    return baseSpeedClick?baseSpeedClick.call(button):undefined;
  };

  // Sanitize any pre-fix browser snapshot that restored RECOVERED together with a stale
  // active fast-forward state. Preserve handledIncidentIds and the recorded episode.
  if(recoveryObserved&&fast)clearFastForwardState();
  updateSpeedControl();

  window.LineAlertRecoveryFastForward={
    clearFastForwardState,
    leaveRecoveredEpisodeForAdvance
  };
})();
