(function(global){
  'use strict';

  // Controlled synthetic demo only. The equations are physical simplifications;
  // the coefficients are illustrative until commissioned against a real asset.
  const CFG={
    classification:'synthetic_demo_only',
    rpm:960,
    effectiveImbalanceMassKg:0.018,
    rollRadiusM:0.110,
    driveTorqueNm:0.550,
    motorTorqueConstantNmPerA:0.420,
    healthyEccentricityM:0.00030,
    problemEccentricityM:0.00065,
    vibrationTransferGainMmSPerN:10.0,
    healthyStartupTensionFraction:0.045,
    healthySettlingTauSec:45,
    problemBaseTensionFraction:0.030,
    problemGrowthTensionFraction:0.080,
    problemGrowthTauSec:180,
    eccentricityGrowthTauSec:150,
    detect:{vibrationRatio:1.50,tensionPeakToPeakN:0.65,currentPeakToPeakA:0.17}
  };

  function clamp(x,a,b){return Math.max(a,Math.min(b,x));}
  function hash32(s){let h=2166136261;for(let i=0;i<String(s).length;i++){h^=String(s).charCodeAt(i);h=Math.imul(h,16777619);}return h>>>0;}
  function rotationalHz(rpm){return rpm/60;}
  function angularVelocityRadS(rpm){return 2*Math.PI*rotationalHz(rpm);}
  function imbalanceForceN(massKg,eccentricityM,rpm){const w=angularVelocityRadS(rpm);return massKg*eccentricityM*w*w;}
  function webTensionN(torqueNm,radiusM){return torqueNm/radiusM;}
  function motorCurrentA(torqueNm,torqueConstantNmPerA){return torqueNm/torqueConstantNmPerA;}
  function round(x,n=3){const p=Math.pow(10,n);return Math.round(x*p)/p;}

  function featureSet(elapsedSec,kind,severity){
    const t=Math.max(0,elapsedSec||0),rpm=CFG.rpm;
    const baseTension=webTensionN(CFG.driveTorqueNm,CFG.rollRadiusM);
    let tensionFraction,eccentricityM;
    if(kind==='healthy'){
      tensionFraction=CFG.healthyStartupTensionFraction*Math.exp(-t/CFG.healthySettlingTauSec);
      eccentricityM=CFG.healthyEccentricityM+0.00008*Math.exp(-t/60);
    }else{
      const sev=clamp(Number.isFinite(severity)?severity:1,0.80,1.25);
      tensionFraction=CFG.problemBaseTensionFraction+CFG.problemGrowthTensionFraction*sev*(1-Math.exp(-t/CFG.problemGrowthTauSec));
      eccentricityM=CFG.healthyEccentricityM+(CFG.problemEccentricityM-CFG.healthyEccentricityM)*sev*(1-Math.exp(-t/CFG.eccentricityGrowthTauSec));
    }
    const forceN=imbalanceForceN(CFG.effectiveImbalanceMassKg,eccentricityM,rpm);
    const vibration1xMmS=forceN*CFG.vibrationTransferGainMmSPerN;
    const tensionPeakToPeakN=2*baseTension*tensionFraction;
    const torquePeakToPeakNm=2*CFG.driveTorqueNm*tensionFraction;
    const currentPeakToPeakA=torquePeakToPeakNm/CFG.motorTorqueConstantNmPerA;
    return{
      rpm:round(rpm,1),
      rotationalFrequencyHz:round(rotationalHz(rpm),2),
      angularVelocityRadS:round(angularVelocityRadS(rpm),2),
      rollRadiusM:CFG.rollRadiusM,
      baseWebTensionN:round(baseTension,2),
      eccentricityMm:round(eccentricityM*1000,3),
      imbalanceForceN:round(forceN,3),
      vibration1xMmS:round(vibration1xMmS,3),
      tensionPeakToPeakN:round(tensionPeakToPeakN,3),
      driveCurrentA:round(motorCurrentA(CFG.driveTorqueNm,CFG.motorTorqueConstantNmPerA),3),
      currentPeakToPeakA:round(currentPeakToPeakA,3),
      elapsedSec:Math.round(t)
    };
  }

  function healthyFeatures(elapsedSec){return featureSet(elapsedSec,'healthy',1);}
  function problemFeatures(elapsedSec,severity){return featureSet(elapsedSec,'problem',severity);}
  function severityForIncident(incidentId){return 0.90+(hash32(String(incidentId)+'|physics-severity')%6)*0.05;}
  function comparison(elapsedSec,severity){
    const problem=problemFeatures(elapsedSec,severity),healthy=healthyFeatures(elapsedSec);
    return{
      problem,healthy,
      vibrationRatio:round(problem.vibration1xMmS/Math.max(0.001,healthy.vibration1xMmS),2),
      tensionDeltaN:round(problem.tensionPeakToPeakN-healthy.tensionPeakToPeakN,3),
      currentDeltaA:round(problem.currentPeakToPeakA-healthy.currentPeakToPeakA,3)
    };
  }
  function detectionSeconds(severity){
    for(let t=0;t<=600;t+=15){
      const c=comparison(t,severity);
      if(c.vibrationRatio>=CFG.detect.vibrationRatio&&c.problem.tensionPeakToPeakN>=CFG.detect.tensionPeakToPeakN&&c.problem.currentPeakToPeakA>=CFG.detect.currentPeakToPeakA)return t;
    }
    return null;
  }
  function episode(incidentId,restartTime,presentationTime,concernTime){
    const severity=severityForIncident(incidentId),rawDetect=detectionSeconds(severity);
    const latestUseful=Number.isFinite(presentationTime)&&Number.isFinite(restartTime)?Math.max(30,presentationTime-restartTime-30):600;
    const detectSec=Math.min(rawDetect==null?latestUseful:rawDetect,latestUseful);
    return{
      incidentId,severity:round(severity,2),restartTime,presentationTime,concernTime,
      detectionSeconds:detectSec,
      detectionTime:Number.isFinite(restartTime)?restartTime+detectSec:null,
      detectionComparison:comparison(detectSec,severity),
      presentationComparison:Number.isFinite(presentationTime)&&Number.isFinite(restartTime)?comparison(Math.max(0,presentationTime-restartTime),severity):null,
      formulas:{
        rotational_frequency:'f = RPM / 60',
        angular_velocity:'omega = 2*pi*f',
        rotating_unbalance_force:'F = m*e*omega^2',
        web_tension_approximation:'T = torque / roll_radius',
        motor_current_approximation:'I = torque / Kt'
      },
      coefficientBoundary:'Vibration sensor response uses an illustrative synthetic transfer gain because real structure mass, stiffness, damping, mounting and resonance are not commissioned.'
    };
  }

  global.LineAlertRollPhysics={CFG,rotationalHz,angularVelocityRadS,imbalanceForceN,webTensionN,motorCurrentA,healthyFeatures,problemFeatures,comparison,detectionSeconds,severityForIncident,episode};
})(window);
