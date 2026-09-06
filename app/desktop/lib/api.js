'use strict';
function createApiClient(getOrigin, {fetchFn = fetch, timeout = 30000} = {}) {
  async function get(endpoint) {
    const origin = getOrigin();
    if (!origin) throw new Error('Engine is not connected.');
    try {
      const response = await fetchFn(`${origin}/api/${endpoint}`, {method:'GET', redirect:'error', signal:AbortSignal.timeout(timeout)});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } catch (error) { throw new Error(`/api/${endpoint}: ${error.message}`, {cause:error}); }
  }
  return Object.freeze({
    health: () => get('health'),
    update: () => get('update'),
    backlog: async () => {
      const value = await get('requests');
      if (!Number.isSafeInteger(value?.open) || value.open < 0) throw new Error('Invalid /api/requests open count.');
      return value.open;
    },
    inbox: async () => {
      const value = await get('inbox');
      if (!Array.isArray(value) || value.some(item => typeof item?.signed !== 'boolean')) throw new Error('Invalid /api/inbox signature state.');
      return value.filter(item => !item.signed).length;
    }
  });
}
module.exports = {createApiClient};
