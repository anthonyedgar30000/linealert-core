(function(){
  'use strict';
  const store=window.LineAlertDemoSession;
  if(!store||!window.LineAlertMaintenanceObserve||typeof store.save!=='function')return;

  const baseSave=store.save.bind(store);
  store.save=function(snapshot){
    if(snapshot&&snapshot.source==='plant_canvas'){
      const maintenance=window.LineAlertMaintenanceObserve.snapshot();
      snapshot.maintenance=maintenance;
      if(maintenance.active){
        snapshot.state='MAINTENANCE';
        snapshot.asset='Labeler 2';
        snapshot.recommendation=null;
        snapshot.recommendationTitle=null;
        snapshot.recommendationWhy=null;
      }else if(maintenance.postMaintenanceObservation){
        snapshot.state='POST_MAINTENANCE_OBSERVE';
        snapshot.asset='Labeler 2';
        snapshot.recommendation=null;
        snapshot.recommendationTitle=null;
        snapshot.recommendationWhy=null;
      }
    }
    return baseSave(snapshot);
  };
})();
