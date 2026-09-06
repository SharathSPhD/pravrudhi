'use strict';
function engineMenu(controller, wrap = fn => fn) {
  return [
    {label:'Restart engine',click:wrap(()=>controller.restart())},
    {label:'Stop engine',click:wrap(()=>controller.stop())},
    {label:'Check for updates',click:wrap(()=>controller.checkForUpdates())},
    {label:'Open workspace folder',click:wrap(()=>controller.openWorkspace())}
  ];
}
function trayState(running, controller, focus, quit, wrap = fn => fn) {
  const label = `Engine ${running ? 'running' : 'stopped'}`;
  return {tooltip:`Pravrudhi — ${label}`,items:[
    {label,enabled:false}, {label:'Open Pravrudhi',click:focus},
    ...engineMenu(controller,wrap).slice(0,2), {label:'Quit',click:quit}
  ]};
}
module.exports = {engineMenu, trayState};
