const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../../qa_manager/web/js/app.js'), 'utf8');

async function harness() {
  const elements = new Map();
  function element() {
    return {textContent: '', children: [], classList: {add() {}, remove() {}},
      querySelectorAll: () => [], append(...children) { this.children.push(...children); },
      replaceChildren(...children) { this.children = children; }, insertBefore() {}, scrollIntoView() {}};
  }
  const select = key => { if (!elements.has(key)) elements.set(key, element()); return elements.get(key); };
  const state = {reply: async () => []};
  const context = vm.createContext({document: {querySelector: select, querySelectorAll: () => [], createElement: element},
    fetch: async url => ({ok: true, status: 200, json: () => state.reply(url)}),
    setTimeout: () => 1, clearTimeout() {}, setInterval() {}, console});
  vm.runInContext(source, context);
  await new Promise(resolve => setImmediate(resolve));
  return {context, elements, state, run: code => vm.runInContext(code, context)};
}

test('Run All ERROR does not overwrite skipped API/E2E or passing system cards', async () => {
  const h = await harness();
  const run = {id: 'run', suite: 'all', status: 'ERROR', started_at: new Date().toISOString(), duration_ms: 5,
    results: [{category: 'system', status: 'PASS'}, {category: 'api', status: 'SKIPPED'},
      {category: 'e2e', status: 'SKIPPED'}, {category: 'security', status: 'ERROR'}]};
  h.state.reply = async url => url.endsWith('/runs') ? [run] : run;
  h.run("active = {id: 'A'}");
  await h.run('loadRuns()');
  assert.equal(h.elements.get('#overall b').textContent, 'ERROR');
  assert.equal(h.elements.get('#systemMetric').textContent, 'PASS');
  assert.equal(h.elements.get('#apiMetric').textContent, 'SKIPPED');
  assert.equal(h.elements.get('#e2eMetric').textContent, 'SKIPPED');
  assert.equal(h.elements.get('#securityMetric').textContent, 'ERROR');
});

test('a delayed response from the previous project cannot overwrite the selected project', async () => {
  const h = await harness(); let release;
  h.state.reply = url => url.includes('/projects/A/') ? new Promise(resolve => { release = resolve; }) : [];
  h.run("active = {id: 'A'}"); const old = h.run('loadRuns()');
  await new Promise(resolve => setImmediate(resolve));
  h.run("active = {id: 'B'}; generation++"); await h.run('loadRuns()');
  release([]); await old;
  assert.equal(h.elements.get('#overall b').textContent, 'NOT RUN');
  assert.equal(h.elements.get('#apiMetric').textContent, 'NOT RUN');
});

test('an unexecuted category in a completed run is not marked PASS', async () => {
  const h = await harness();
  assert.equal(h.run("categoryStatus({status:'ERROR', results:[]}, 'e2e')"), 'NOT RUN');
  assert.equal(h.run("categoryStatus({status:'RUNNING', current_stage:'System', results:[]}, 'api')"), 'QUEUED');
});
