'use strict';
const quote = value => `'${String(value).replaceAll("'", "'\\''")}'`;
function recovery(check, binary, workspace, platform = process.platform) {
  const cli = quote(binary || 'pravrudhi'), root = ` --root ${quote(workspace)}`;
  if (check.ok) return {command:`${cli} doctor --json${root}`, label:'Copy recheck command'};
  if (['initialised','prereg'].includes(check.name) || (check.name === 'ledger' && check.detail.includes('Cannot read'))) return {command:`${cli} init${root}`,label:'Copy setup command'};
  if (check.name === 'pools') return {command:`${cli} pool seal-mbppplus${root}`,label:'Copy seal command',note:'Prepares the MBPP+ benchmark. For another benchmark, follow the engine quickstart.'};
  if (check.name === 'docker' && platform === 'linux' && check.detail.includes('Permission denied')) return {command:'sudo usermod -aG docker "$USER"',label:'Copy fix command',note:'Log out and back in after changing group membership.'};
  if (check.name === 'docker' && check.detail.includes('daemon is not running')) return {command:platform === 'darwin' ? 'open -a Docker' : 'sudo systemctl start docker',label:'Copy start command',note:platform === 'darwin' ? 'Requires Docker Desktop.' : 'For installations managed by systemd.'};
  return {command:`${cli} doctor --json${root}`,label:'Copy diagnostic command',note:check.name === 'ledger' ? 'Restore a verified ledger backup; there is no safe automatic repair command.' : 'Follow the installation instructions for this check, then rerun doctor.'};
}
module.exports = {recovery};
