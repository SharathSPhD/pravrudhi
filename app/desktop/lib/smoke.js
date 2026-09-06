'use strict';
const {writeState} = require('./core');
function createSmokeReporter(file, {write = writeState} = {}) {
  const report = {launched:false,engine_found:false,engine_url:null,page_title:null,health_ok:false,errors:[]};
  const save = () => { write(file,report); return report.errors.length ? 1 : 0; };
  return {
    launched: () => { report.launched = true; },
    engine: origin => { report.engine_found = true; report.engine_url = origin; },
    async finish({getTitle,health}) {
      try {
        report.page_title = await getTitle();
        report.health_ok = (await health())?.ok === true;
        if (!report.launched) throw new Error('Main window did not finish loading.');
        if (!report.engine_found || !report.engine_url) throw new Error('No engine found.');
        if (!report.page_title) throw new Error('Engine page has no title.');
        if (!report.health_ok) throw new Error('Engine health was not ok.');
      } catch (error) { report.errors.push(error.message); }
      return save();
    },
    async fail(error) { report.errors.push(error.message || String(error)); return save(); }
  };
}
module.exports = {createSmokeReporter};
