'use strict';
const { contextBridge, ipcRenderer } = require('electron');
contextBridge.exposeInMainWorld('desktop', Object.freeze({
  engineStatus: () => ipcRenderer.invoke('engine:status'),
  locateEngine: () => ipcRenderer.invoke('engine:locate'),
  restart: () => ipcRenderer.invoke('engine:restart'),
  stop: () => ipcRenderer.invoke('engine:stop'),
  doctor: () => ipcRenderer.invoke('engine:doctor'),
  checkForUpdates: () => ipcRenderer.invoke('engine:updates'),
  openWorkspace: () => ipcRenderer.invoke('engine:workspace')
}));
