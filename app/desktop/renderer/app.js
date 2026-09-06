'use strict';
const $ = id => document.getElementById(id);
let previousChecks = '', pending = false;
async function action(name) {
  if (pending) return;
  pending = true; $('action-error').textContent = '';
  try { await window.desktop[name](); } catch(e) { $('action-error').textContent = e.message; }
  finally { pending = false; await refresh(); }
}
for (const [id,name] of Object.entries({'locate':'locateEngine','restart':'restart','stop':'stop','doctor':'doctor','open-workspace':'openWorkspace'})) $(id).addEventListener('click', () => action(name));
function copyButton(text,label) {
  const button = document.createElement('button'); button.className = 'secondary'; button.textContent = label;
  button.addEventListener('click', async () => {
    try {
      // File-origin fallback avoids adding a privileged clipboard IPC surface.
      const input = document.createElement('textarea'); input.value = text; document.body.append(input); input.select();
      const copied = document.execCommand('copy'); input.remove();
      if (!copied) throw new Error('Copy unavailable. Select and copy the displayed command.');
      button.textContent = 'Copied'; setTimeout(() => { button.textContent = label; },1500);
    } catch(e) { $('action-error').textContent = e.message; }
  }); return button;
}
async function refresh() {
  try {
    const s = await window.desktop.engineStatus();
    $('title').textContent = ({starting:'Preparing your workspace',missing:'Bring your engine to the desktop',error:'Your engine needs attention',stopped:'Your workspace is paused',running:'Your workspace is ready'})[s.phase];
    $('badge').textContent = s.phase === 'starting' ? 'Connecting' : s.phase;
    $('detail').textContent = s.detail; $('workspace').textContent = s.workspace;
    $('shell-version').textContent = `Shell ${s.shellVersion} · Engine ${s.version}`;
    $('doctor').disabled = !s.binary || s.doctorBusy;
    $('stop').disabled = !['starting','running'].includes(s.phase);
    $('doctor-state').textContent = s.doctorBusy ? 'Running pravrudhi doctor --json…' : s.doctorError || (s.checks.length ? 'Checks reported by your installed engine. Recovery commands are copied, never executed by the shell.' : 'Checks appear here if the engine cannot start.');
    const key = JSON.stringify(s.checks);
    if (key !== previousChecks) {
      previousChecks = key; $('checks').replaceChildren();
      for (const c of s.checks) {
        const row = document.createElement('article'); row.className = 'check';
        const heading = document.createElement('strong'); heading.className = c.ok ? 'pass':'fail'; heading.textContent = `${c.ok ? '✓':'!'}  ${c.name}`;
        const detail = document.createElement('p'); detail.textContent = c.detail;
        const controls = document.createElement('div'); controls.className = 'recovery';
        const code = document.createElement('code'); code.textContent = c.recovery.command;
        controls.append(code,copyButton(c.recovery.command,c.recovery.label)); row.append(heading,detail,controls);
        if(c.recovery.note) { const note = document.createElement('small'); note.textContent = c.recovery.note; row.append(note); }
        $('checks').append(row);
      }
    }
  } catch(e) { $('action-error').textContent = e.message; }
}
async function tick() { await refresh(); setTimeout(tick,500); } tick();
