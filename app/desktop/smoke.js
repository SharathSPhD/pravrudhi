'use strict';
const {spawn, spawnSync} = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const {createSmokeReporter} = require('./lib/smoke');
const {terminateGroup} = require('./lib/lifecycle');
const reportFile = path.join(__dirname,'.smoke/report.json');
const failure = async error => {
  console.error(`Desktop smoke failed: ${error.message}`);
  await createSmokeReporter(reportFile).fail(error);
  process.exitCode = 1;
};
async function main() {
  // Never let a report from a previous launch pass this run.
  fs.rmSync(reportFile,{force:true});
  const env = {...process.env,ELECTRON_ENABLE_LOGGING:'1',PRAVRUDHI_DESKTOP_SMOKE:'1'};
  const electron = require('electron');
  const hasXvfb = !spawnSync('xvfb-run',['--help'],{stdio:'ignore'}).error;
  // This environment cannot configure the root-owned SUID sandbox helper.
  // BrowserWindow's sandboxed, isolated renderer remains enabled.
  const args = [__dirname,'--no-sandbox','--disable-dev-shm-usage'];
  if (!hasXvfb) {
    env.ELECTRON_DISABLE_GPU = '1';
    args.push('--headless','--ozone-platform=headless','--disable-gpu');
  }
  const child = spawn(hasXvfb ? 'xvfb-run' : electron,hasXvfb ? ['-a',electron,...args] : args,{env,stdio:'inherit',detached:true});
  let timedOut = false;
  const timer = setTimeout(()=> {
    timedOut = true;
    terminateGroup(child,{grace:5000}).catch(error=>console.error(error));
  },120000);
  const forward = () => terminateGroup(child,{grace:5000}).catch(error=>console.error(error));
  process.once('SIGINT',forward); process.once('SIGTERM',forward);
  child.once('error',async error=> { clearTimeout(timer); await failure(error); });
  child.once('close',async (code,signal)=> {
    clearTimeout(timer); process.removeListener('SIGINT',forward);process.removeListener('SIGTERM',forward);
    try {
      const report = JSON.parse(fs.readFileSync(reportFile,'utf8'));
      if (timedOut || code !== 0 || report.launched !== true || report.engine_found !== true || report.health_ok !== true || !report.engine_url || !report.page_title || !Array.isArray(report.errors) || report.errors.length) {
        throw new Error(timedOut ? 'Launch timed out.' : report.errors?.join('; ') || `Electron exited ${signal || code} without a successful report.`);
      }
      console.log(`Loaded ${report.engine_url}: ${report.page_title}`);
      process.exitCode = 0;
    } catch (error) {
      // Preserve main-process observations on failure; only create a fallback if
      // Electron could not initialize far enough to write its own report.
      if (fs.existsSync(reportFile)) { console.error(`Desktop smoke failed: ${error.message}`); process.exitCode = 1; }
      else await failure(new Error(timedOut ? 'Launch timed out before reporting.' : `Electron exited ${signal || code}: ${error.message}`));
    }
  });
}
main().catch(failure);
