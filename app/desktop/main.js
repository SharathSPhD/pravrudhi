'use strict';
const {app, BrowserWindow, Menu, Tray, nativeImage, ipcMain, dialog, shell, screen} = require('electron');
const {spawn} = require('node:child_process');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const {discoverEngine, freePort, pollHealth, parseDoctor, linkPolicy, readState, writeState, validBounds} = require('./lib/core');
const {recovery} = require('./lib/recovery');
const docs = 'https://github.com/SharathSPhD/pravrudhi#readme';
const statusFile = path.join(__dirname, 'renderer/index.html');
const statusURL = pathToFileURL(statusFile).href;
let settings, stateFile, workspace, tray, engine, controller, quitting = false, queue = Promise.resolve();
const windows = new Set(), children = new Set();
let status = {phase: 'starting', detail: 'Finding your installed engine…', checks: [], version: 'Unknown', origin: null};
function persist() { writeState(stateFile, settings); }
function publish(patch) { status = {...status, ...patch}; refreshTray(); }
function statusScreens() { for (const w of windows) w.loadFile(statusFile).catch(() => {}); }
function focus() { const w = [...windows][0] || createWindow(); if (w.isMinimized()) w.restore(); w.show(); w.focus(); }
function safe(action) { return () => Promise.resolve().then(action).catch(e => dialog.showErrorBox('Pravrudhi', e.message)); }
function serialize(action) { controller?.abort(); const next = queue.then(action); queue = next.catch(() => {}); return next; }
function launch(args) {
  if (quitting) throw new Error('Application is shutting down.');
  const child = spawn(status.binary, args, {cwd: workspace, detached: true, stdio: ['ignore', 'pipe', 'pipe'], shell: false});
  children.add(child);
  return child;
}
function signalGroup(child, signal) { if (child.pid) { try { process.kill(-child.pid, signal); } catch (e) { if (e.code !== 'ESRCH') throw e; } } }
async function terminate(child) {
  signalGroup(child, 'SIGTERM');
  await new Promise(r => setTimeout(r, 800));
  signalGroup(child, 'SIGKILL'); children.delete(child);
}
async function command(args, timeout = 30000) {
  if (!status.binary) throw new Error('Locate an installed engine first.');
  const child = launch(args);
  return new Promise((resolve, reject) => {
    let out = '', err = '', finished = false;
    const finish = async (error) => { if (finished) return; finished = true; clearTimeout(timer); await terminate(child); error ? reject(error) : resolve(out); };
    const timer = setTimeout(() => finish(new Error('Engine command timed out.')), timeout);
    child.stdout.on('data', b => { out += b; if (out.length > 4 * 1024 * 1024) finish(new Error('Engine output exceeded the limit.')); });
    child.stderr.on('data', b => { err = (err + b).slice(-12000); });
    child.once('error', e => finish(e));
    child.once('close', code => finish(code && !out.trim() ? new Error(err || `Engine exited with code ${code}`) : null));
  });
}
async function doctor() {
  publish({doctorBusy: true});
  try { const checks = parseDoctor(await command(['doctor', '--json', '--root', workspace])).map(check => ({...check, recovery:recovery(check,status.binary,workspace)})); publish({checks, doctorError: null}); return checks; }
  catch (e) { publish({doctorError: e.message}); return []; }
  finally { publish({doctorBusy: false}); }
}
async function stop() {
  controller?.abort();
  const old = engine; engine = null;
  if (old) await terminate(old);
  publish({phase:'stopped', origin:null, detail:'Engine stopped. Your workspace is ready when you are.'}); statusScreens();
}
async function start() {
  await stop();
  if (quitting) return;
  publish({phase:'starting', detail:'Finding your installed engine…', checks:[], doctorError:null});
  const binary = await discoverEngine({saved: settings.enginePath});
  publish({binary, version:'Unknown'});
  if (!binary) { publish({phase:'missing', detail:'Connect your Pravrudhi engine to get started.'}); return; }
  command(['--version'], 5000).then(value => { if (status.binary === binary) publish({version:value.trim() || 'Unknown'}); }).catch(() => {});
  controller = new AbortController();
  const currentController = controller;
  let processFailure = '';
  try {
    const port = await freePort();
    currentController.signal.throwIfAborted();
    const origin = `http://127.0.0.1:${port}`;
    publish({detail:`Starting ${binary} · waiting for /api/health…`});
    const child = launch(['app', '--no-browser', '--port', String(port), '--root', workspace]); engine = child;
    let stderr = '';
    child.stderr.on('data', b => { stderr = (stderr + b).slice(-6000); }); child.stdout.resume();
    child.on('error', e => { processFailure = e.message; currentController.abort(); });
    child.on('exit', (code, signal) => {
      if (engine !== child) return;
      processFailure = stderr || `Engine exited (${signal || code}).`; currentController.abort();
      if (status.phase === 'running') { engine = null; publish({phase:'error', origin:null, detail:processFailure}); statusScreens(); safe(async () => { await terminate(child); if (!quitting) await doctor(); })(); }
    });
    try { await pollHealth(`${origin}/api/health`, {signal:currentController.signal}); } catch(e) { throw new Error(processFailure || e.message); }
    const response = await fetch(origin, {signal: AbortSignal.timeout(5000)});
    if (!response.ok || !(response.headers.get('content-type') || '').includes('text/html')) throw new Error('The engine is healthy, but its frontend is not installed. See the installation instructions to prepare the interface.');
    currentController.signal.throwIfAborted();
    publish({phase:'running', origin, detail:'Engine running'});
    for (const w of windows) await w.loadURL(origin);
  } catch (e) {
    const old = engine; engine = null; if (old) await terminate(old);
    if (quitting || (currentController.signal.aborted && !processFailure)) return;
    publish({phase:'error', origin:null, detail:e.message}); statusScreens(); await doctor();
  }
}
async function locate() {
  const result = await dialog.showOpenDialog({title:'Locate the Pravrudhi engine executable', properties:['openFile']});
  if (!result.canceled) { settings.enginePath = result.filePaths[0]; persist(); await serialize(start); }
  return status;
}
let updating = false;
async function updates() {
  if (updating) return;
  updating = true;
  try {
    const result = JSON.parse(await command(['update', '--json', '--root', workspace]));
    if (result.update_available === true) {
      const choice = await dialog.showMessageBox({type:'question', message:`Engine update available: ${result.latest?.tag || 'new release'}`, detail:'Apply the release using the engine’s update safeguards?', buttons:['Cancel','Apply update'], defaultId:0, cancelId:0});
      if (choice.response === 1) {
        const applied = JSON.parse(await command(['update','--apply','--channel','release','--json','--root',workspace], 300000));
        if (typeof applied.reason !== 'string') throw new Error('The engine returned an update result without a reason.');
        await dialog.showMessageBox({message:'Engine update', detail: applied.reason, buttons:['OK']});
      }
    } else await dialog.showMessageBox({message:result.latest ? 'Your engine is up to date.' : 'Could not check for updates.', detail:JSON.stringify(result, null, 2)});
    return result;
  } finally { updating = false; }
}
function createWindow() {
  const b = settings.bounds;
  const visible = validBounds(b) && screen.getAllDisplays().some(d => b.x < d.workArea.x + d.workArea.width && b.x + b.width > d.workArea.x && b.y < d.workArea.y + d.workArea.height && b.y + b.height > d.workArea.y);
  const w = new BrowserWindow({width:1200, height:800, ...(visible ? b : {}), minWidth:720, minHeight:520, title:'Pravrudhi', backgroundColor:'#11151b', show:false, icon:path.join(__dirname,'renderer/icon.png'), webPreferences:{preload:path.join(__dirname,'preload.js'), contextIsolation:true, nodeIntegration:false, sandbox:true}});
  windows.add(w);
  w.once('ready-to-show', () => { w.show(); if (settings.maximized) w.maximize(); });
  const remember = () => { if (!w.isDestroyed()) { settings.bounds = w.getNormalBounds(); settings.maximized = w.isMaximized(); persist(); } };
  w.on('close', remember); w.on('resize', remember); w.on('move', remember); w.on('closed', () => windows.delete(w));
  const navigate = (event, url) => {
    if (linkPolicy(url,status.origin) === 'internal') return;
    event.preventDefault(); if (linkPolicy(url,status.origin) === 'external') safe(() => shell.openExternal(url))();
  };
  w.webContents.setWindowOpenHandler(({url}) => { if (linkPolicy(url,status.origin) === 'external') safe(() => shell.openExternal(url))(); else if (linkPolicy(url,status.origin) === 'internal') w.loadURL(url).catch(() => {}); return {action:'deny'}; });
  w.webContents.on('will-navigate', navigate); w.webContents.on('will-redirect', navigate);
  w.webContents.on('will-attach-webview', event => event.preventDefault());
  w.webContents.session.setPermissionRequestHandler((_wc, _permission, callback) => callback(false));
  w.webContents.on('did-fail-load', (_event, code, detail, _url, main) => { if (main && code !== -3) { publish({phase:'error',detail:`Could not load the interface: ${detail}`}); w.loadFile(statusFile).catch(() => {}); } });
  if (status.origin) w.loadURL(status.origin).catch(() => {}); else w.loadFile(statusFile).catch(() => {});
  return w;
}
function refreshTray() {
  tray?.setToolTip(`Pravrudhi — Engine ${status.phase === 'running' ? 'running' : 'stopped'}`);
  tray?.setContextMenu(Menu.buildFromTemplate([{label:`Engine ${status.phase === 'running' ? 'running' : 'stopped'}`,enabled:false},{label:'Open Pravrudhi',click:focus},{label:'Restart engine',click:safe(() => serialize(start))},{label:'Quit',click:() => app.quit()}]));
}
async function shutdown() { controller?.abort(); engine = null; await Promise.all([...children].map(terminate)); }
if (!app.requestSingleInstanceLock()) app.quit();
else {
  app.on('second-instance', () => { if (settings) focus(); });
  app.on('window-all-closed', () => app.quit());
  app.on('before-quit', event => { if (!quitting) { event.preventDefault(); quitting = true; shutdown().finally(() => app.quit()); } });
  for (const signal of ['SIGINT','SIGTERM']) process.on(signal, () => app.quit());
  app.whenReady().then(() => {
    stateFile = path.join(app.getPath('userData'), 'desktop-state.json'); settings = readState(stateFile);
    workspace = path.resolve(process.env.PRAVRUDHI_WORKSPACE || settings.workspace || app.getPath('home')); settings.workspace = workspace;
    const handlers = {'engine:status':() => ({...status,workspace,shellVersion:app.getVersion()}), 'engine:locate':locate,'engine:restart':() => serialize(start),'engine:stop':() => serialize(stop),'engine:doctor':doctor,'engine:updates':updates,'engine:workspace':() => shell.openPath(workspace)};
    for (const [channel, handler] of Object.entries(handlers)) ipcMain.handle(channel, (event) => {
      const url = event.senderFrame?.url;
      if (!windows.has(BrowserWindow.fromWebContents(event.sender)) || event.senderFrame !== event.sender.mainFrame || !(url === statusURL || linkPolicy(url,status.origin) === 'internal')) throw new Error('Untrusted desktop request');
      return handler();
    });
    Menu.setApplicationMenu(Menu.buildFromTemplate([
      {label:'File',submenu:[{label:'New Window',accelerator:'CmdOrCtrl+N',click:createWindow},{label:'Locate engine…',click:safe(locate)},{type:'separator'},{role:'quit'}]},
      {role:'editMenu'},
      {label:'View',submenu:[{role:'reload'},{role:'resetZoom'},{role:'zoomIn'},{role:'zoomOut'},{type:'separator'},{role:'toggleDevTools'},{role:'togglefullscreen'}]},
      {label:'Engine',submenu:[{label:'Restart engine',click:safe(() => serialize(start))},{label:'Stop engine',click:safe(() => serialize(stop))},{label:'Open workspace folder',click:safe(() => shell.openPath(workspace))},{label:'Choose workspace…',click:safe(async () => { const r = await dialog.showOpenDialog({properties:['openDirectory']}); if (!r.canceled) { workspace = r.filePaths[0]; settings.workspace = workspace; persist(); await serialize(start); } })},{type:'separator'},{label:'Check for updates',click:safe(updates)}]},
      {label:'Help',submenu:[{label:'Documentation',click:safe(() => shell.openExternal(docs))},{label:'About Pravrudhi',click:safe(() => dialog.showMessageBox({message:'Pravrudhi',detail:`Desktop ${app.getVersion()}\nEngine ${status.version}\n${status.binary || 'No engine located'}\nWorkspace: ${workspace}`}))}]}
    ]));
    // A bundled, generated bitmap keeps the tray independent of system icon themes.
    const pixels = Buffer.alloc(24 * 24 * 4);
    for (let y=3;y<21;y++) for(let x=5;x<19;x++) if(x<9 || (y<13 && (y<7 || y>9 || x>14))) { const i=(y*24+x)*4; pixels[i]=168; pixels[i+1]=208; pixels[i+2]=120; pixels[i+3]=255; }
    tray = new Tray(nativeImage.createFromBitmap(pixels,{width:24,height:24})); tray.on('click',focus); refreshTray();
    createWindow(); safe(() => serialize(start))();
    app.on('activate',focus);
  }).catch(e => { dialog.showErrorBox('Pravrudhi',e.message); app.quit(); });
}
