const $ = s => document.querySelector(s), $$ = s => document.querySelectorAll(s);
const categories = ['system', 'api', 'e2e', 'security'];
let projects = [], active = null, poll, generation = 0, refreshVersion = 0;
let testsProjectId = null, detailVersion = 0;

async function api(path, options = {}) {
  const response = await fetch('/api' + path, {headers: {'Content-Type': 'application/json'}, ...options});
  if (!response.ok) {
    const error = await response.json().catch(() => ({detail: response.statusText}));
    throw Error(typeof error.detail === 'string' ? error.detail : JSON.stringify(error.detail));
  }
  return response.status === 204 ? null : response.json();
}
function toast(message) {
  $('#toast').textContent = message; $('#toast').classList.add('show');
  setTimeout(() => $('#toast').classList.remove('show'), 5000);
}
function node(tag, text, className) {
  const element = document.createElement(tag);
  if (text != null) element.textContent = text;
  if (className) element.className = className;
  return element;
}
function badge(status) { return node('span', status, 'badge ' + status); }
function aggregate(results) {
  const states = results.map(result => result.status);
  for (const status of ['ERROR', 'FAIL', 'WARNING', 'RUNNING', 'QUEUED']) if (states.includes(status)) return status;
  return states.includes('PASS') ? 'PASS' : states.length ? 'SKIPPED' : 'NOT RUN';
}
function categoryStatus(run, category) {
  const results = (run.results || []).filter(result => result.category === category);
  if (results.length) return aggregate(results);
  if (['RUNNING', 'QUEUED'].includes(run.status)) return run.current_stage?.toLowerCase() === category ? 'RUNNING' : 'QUEUED';
  return 'NOT RUN';
}
async function loadProjects(preferred) {
  projects = await api('/projects');
  active = projects.find(project => project.id === (preferred || active?.id)) || projects[0] || null;
  renderTabs(); await render();
}
function renderTabs() {
  $('#tabs').querySelectorAll('.project').forEach(element => element.remove());
  projects.forEach(project => {
    const button = node('button', (project.enabled ? '● ' : '○ ') + project.name, 'project ' + (project.id === active?.id ? 'active' : ''));
    button.onclick = () => { active = project; renderTabs(); render().catch(error => toast(error.message)); };
    $('#tabs').insertBefore(button, $('#addTab'));
  });
}
async function render() {
  generation++; detailVersion++; clearTimeout(poll);
  $('#empty').hidden = !!active; $('#dashboard').hidden = !active;
  $('#runAll').disabled = !active || !active.enabled; $('#runDetail').hidden = true;
  $('#overall').className = 'status neutral'; $('#overall b').textContent = 'NOT RUN';
  categories.forEach(category => { $('#' + category + 'Metric').textContent = 'NOT RUN'; });
  $('#runs').replaceChildren(); $('#testSummary').textContent = '';
  if (!active) return;
  $('#projectName').textContent = active.name;
  $('#projectUrl').textContent = active.frontend_url; $('#projectUrl').href = active.frontend_url;
  $$('[data-run]').forEach(button => { button.disabled = !active.enabled; });
  await Promise.all([loadRuns(), loadTestSummary()]);
}
async function loadRuns() {
  clearTimeout(poll);
  if (!active) return;
  const id = active.id, currentGeneration = generation, version = ++refreshVersion;
  const current = () => active?.id === id && generation === currentGeneration && refreshVersion === version;
  try {
    const runs = await api(`/projects/${id}/runs`);
    const relevant = categories.map(category => runs.find(run => run.suite === category || run.suite === 'all')).filter(Boolean);
    const details = await Promise.all([...new Set(relevant.map(run => run.id))].map(runId => api(`/runs/${runId}`)));
    if (!current()) return;
    const box = $('#runs'); box.replaceChildren();
    if (!runs.length) box.append(node('p', '아직 실행 이력이 없습니다. 기본 테스트를 추가한 뒤 System Check부터 실행하세요.', 'muted'));
    runs.slice(0, 20).forEach(run => {
      const row = node('div', null, 'run'), button = node('button', run.suite.toUpperCase() + ' 상세');
      button.onclick = () => showRun(run.id).catch(error => toast(error.message));
      const elapsed = run.duration_ms == null ? Math.max(0, Date.now() - new Date(run.started_at)) : run.duration_ms;
      row.append(badge(run.status), button, node('span', new Date(run.started_at).toLocaleString() + (run.current_stage ? ' · ' + run.current_stage : '')), node('span', (elapsed / 1000).toFixed(1) + 's'));
      box.append(row);
    });
    $('#overall').className = 'status ' + (runs[0]?.status || 'neutral');
    $('#overall b').textContent = runs[0]?.status || 'NOT RUN';
    categories.forEach(category => {
      const summary = runs.find(run => run.suite === category || run.suite === 'all');
      const detail = details.find(run => run.id === summary?.id);
      $('#' + category + 'Metric').textContent = detail ? categoryStatus(detail, category) : 'NOT RUN';
    });
  } catch (error) { if (current()) toast('결과 조회 실패: ' + error.message); }
  finally { if (current()) poll = setTimeout(loadRuns, 2500); }
}
async function showRun(id) {
  const projectId = active?.id, version = ++detailVersion, run = await api(`/runs/${id}`);
  if (projectId !== active?.id || version !== detailVersion) return;
  const box = $('#runDetail'); box.hidden = false; box.replaceChildren();
  box.append(node('h2', run.suite.toUpperCase() + ' · ' + run.status), node('p', new Date(run.started_at).toLocaleString()));
  for (const result of run.results) {
    const item = node('article', null, 'result');
    item.append(badge(result.status), node('h3', result.category.toUpperCase() + ' · ' + result.test_name), node('p', result.message));
    if (Object.keys(result.details || {}).length) {
      const details = node('details'); details.append(node('summary', '검사 데이터 / 로그'), node('pre', JSON.stringify(result.details, null, 2))); item.append(details);
    }
    for (const artifact of result.artifacts || []) {
      const link = node('a', artifact.type + ' 다운로드', 'artifact'); link.href = `/api/artifacts/${encodeURIComponent(artifact.id)}`; item.append(link);
    }
    box.append(item);
  }
  if (!run.results.length) box.append(node('p', '결과를 수집 중입니다. 잠시 후 상세 버튼을 다시 누르세요.'));
  for (const alert of run.alerts || []) box.append(node('p', `${alert.risk} · ${alert.name} · ${alert.url}\n${alert.description}`));
  box.scrollIntoView({behavior: 'smooth', block: 'start'});
}
async function loadTestSummary() {
  if (!active) return;
  const id = active.id;
  const [cases, scenarios] = await Promise.all([api(`/projects/${id}/api-tests`), api(`/projects/${id}/scenarios`)]);
  if (active?.id === id) $('#testSummary').textContent = `활성 API 테스트 ${cases.filter(item => item.enabled).length}개 · 활성 E2E 시나리오 ${scenarios.filter(item => item.enabled).length}개. 미등록 검사는 SKIPPED입니다.`;
}
function openForm(edit = false) {
  const form = $('#projectForm'); form.reset(); form.elements.enabled.checked = true;
  $('#formError').textContent = ''; $('#deleteProject').hidden = !edit; $('#formTitle').textContent = edit ? 'Edit project' : 'Add project';
  if (edit && active) for (const [key, value] of Object.entries(active)) if (form.elements[key]) {
    if (key === 'enabled') form.elements[key].checked = value;
    else form.elements[key].value = Array.isArray(value) ? value.join(key.endsWith('_urls') ? '\n' : ', ') : (value ?? '');
  }
  $('#projectDialog').showModal();
}
$('#projectForm').onsubmit = async event => {
  event.preventDefault(); const form = event.currentTarget, data = Object.fromEntries(new FormData(form));
  data.enabled = form.elements.enabled.checked;
  data.expected_ports = data.expected_ports.split(',').map(value => value.trim()).filter(Boolean).map(Number);
  data.process_rules = data.process_rules.split(',').map(value => value.trim()).filter(Boolean);
  for (const key of ['backend_urls', 'health_urls']) data[key] = data[key].split(/\r?\n/).map(value => value.trim()).filter(Boolean);
  if (!data.project_path) data.project_path = null;
  try {
    const project = await api(data.id ? `/projects/${data.id}` : '/projects', {method: data.id ? 'PUT' : 'POST', body: JSON.stringify(data)});
    $('#projectDialog').close(); await loadProjects(project.id); toast('Project saved');
  } catch (error) { $('#formError').textContent = error.message; }
};
$('#deleteProject').onclick = async () => {
  if (!active || !confirm(`${active.name} 프로젝트와 등록된 테스트, 실행 이력을 삭제할까요? 대상 프로젝트의 소스 파일은 삭제하지 않습니다.`)) return;
  try { await api(`/projects/${active.id}`, {method: 'DELETE'}); $('#projectDialog').close(); active = null; await loadProjects(); }
  catch (error) { $('#formError').textContent = error.message; }
};
$$('[data-close]').forEach(button => { button.onclick = () => $('#projectDialog').close(); });
$$('[data-dismiss]').forEach(button => { button.onclick = () => button.closest('dialog').close(); });
$$('[data-add]').forEach(button => { button.onclick = () => openForm(); });
$('#addTab').onclick = () => openForm(); $('#editProject').onclick = () => openForm(true); $('#refresh').onclick = loadRuns;
async function run(suite) {
  if (!active) return;
  try { await api(`/projects/${active.id}/run/${suite}`, {method: 'POST', body: '{}'}); toast(`${suite.toUpperCase()} queued`); await loadRuns(); }
  catch (error) { toast(error.message); }
}
$$('[data-run]').forEach(button => { button.onclick = () => run(button.dataset.run); });
$('#runAll').onclick = () => run('all');
async function checkReadiness() {
  $('#readiness').textContent = '확인 중…';
  try {
    const state = await api('/system/readiness');
    $('#readiness').textContent = `실행 Python: ${state.python}\npsutil: ${state.packages.psutil ? '설치됨' : '미설치'}\nPlaywright: ${state.packages.playwright ? '설치됨' : '미설치'}\nChromium: ${state.chromium ? '설치됨' : state.browser_message}\nZAP: ${state.zap.running ? '연결됨' : '연결 안 됨 — ' + state.zap.message}`;
  } catch (error) { $('#readiness').textContent = '준비 상태 조회 실패. 변경된 Python 코드를 적용하려면 QAROZ 서버를 재시작하세요. ' + error.message; }
}
$('#setup').onclick = async () => {
  $('#setupDialog').showModal(); $('#setupError').textContent = '';
  try {
    const settings = await api('/settings'); $('#zapUrl').value = settings.zap_api_url;
    $('#securityEnabled').checked = settings.security_enabled === 'true';
  } catch (error) { $('#setupError').textContent = error.message; }
  await checkReadiness();
};
$('#checkReadiness').onclick = checkReadiness;
$('#saveSettings').onclick = async () => {
  try {
    await api('/settings', {method: 'PUT', body: JSON.stringify({zap_api_url: $('#zapUrl').value, security_enabled: $('#securityEnabled').checked})});
    $('#setupError').textContent = ''; toast('설정 저장 완료');
  } catch (error) { $('#setupError').textContent = error.message; }
};
async function refreshTests() {
  const id = testsProjectId;
  const [cases, scenarios] = await Promise.all([api(`/projects/${id}/api-tests`), api(`/projects/${id}/scenarios`)]);
  if (id !== testsProjectId) return;
  const list = $('#testList'); list.replaceChildren();
  for (const [label, items, endpoint] of [['API', cases, 'api-tests'], ['E2E', scenarios, 'scenarios']]) {
    list.append(node('h3', label + ' · ' + items.length));
    items.forEach(item => {
      const row = node('div', null, 'test-item'), remove = node('button', '삭제');
      remove.onclick = async () => {
        if (!confirm(`Delete ${item.name}?`)) return;
        try { await api(`/${endpoint}/${item.id}`, {method: 'DELETE'}); await refreshTests(); await loadTestSummary(); }
        catch (error) { $('#testsError').textContent = error.message; }
      };
      const description = node('details'); description.append(node('summary', item.name + (item.enabled ? '' : ' (비활성)')), node('pre', JSON.stringify(item, null, 2)));
      row.append(description, remove); list.append(row);
    });
  }
}
$('#manageTests').onclick = async () => {
  if (!active) return;
  testsProjectId = active.id; $('#testsProject').textContent = active.name; $('#testsError').textContent = '';
  $('#apiForm').elements.url.value = (active.backend_urls?.[0] || active.backend_url || active.frontend_url) + '/'; $('#testsDialog').showModal();
  try { await refreshTests(); } catch (error) { $('#testsError').textContent = error.message; }
};
for (const [formId, endpoint] of [['apiForm', 'api-tests'], ['scenarioForm', 'scenarios']]) {
  $('#' + formId).onsubmit = async event => {
    event.preventDefault(); const form = event.currentTarget;
    try {
      const data = Object.fromEntries(new FormData(form));
      if (endpoint === 'api-tests') {
        data.expected_status = Number(data.expected_status); data.assertions = JSON.parse(data.assertions); data.body = JSON.parse(data.body || 'null');
        if (!data.assertions || Array.isArray(data.assertions) || typeof data.assertions !== 'object') throw Error('Assertions는 JSON 객체여야 합니다.');
      } else {
        data.steps = JSON.parse(data.steps); data.expected = JSON.parse(data.expected);
        if (!Array.isArray(data.steps) || !data.steps.length || !Array.isArray(data.expected) || !data.expected.length) throw Error('Steps와 Expected는 비어 있지 않은 JSON 배열이어야 합니다.');
      }
      await api(`/projects/${testsProjectId}/${endpoint}`, {method: 'POST', body: JSON.stringify(data)});
      $('#testsError').textContent = ''; await refreshTests(); await loadTestSummary(); toast('테스트 등록 완료');
    } catch (error) { $('#testsError').textContent = error.message; }
  };
}
$('#starter').onclick = async () => {
  if (!active) return;
  const project = active; $('#starter').disabled = true;
  try {
    const [cases, scenarios] = await Promise.all([api(`/projects/${project.id}/api-tests`), api(`/projects/${project.id}/scenarios`)]);
    if (!cases.some(item => item.name === 'Frontend HTTP smoke')) await api(`/projects/${project.id}/api-tests`, {method: 'POST', body: JSON.stringify({name: 'Frontend HTTP smoke', url: project.frontend_url + '/', expected_status: 200})});
    if (!scenarios.some(item => item.name === 'Frontend page smoke')) await api(`/projects/${project.id}/scenarios`, {method: 'POST', body: JSON.stringify({name: 'Frontend page smoke', steps: [{action: 'goto', url: '/'}, {action: 'wait', selector: 'body'}], expected: [{type: 'visible', selector: 'body'}]})});
    await loadTestSummary(); toast('기본 연결 테스트 준비 완료. 업무 기능 검사는 별도 등록하세요.');
  } catch (error) { toast(error.message); }
  finally { $('#starter').disabled = false; }
};
setInterval(() => { $('#clock').textContent = new Date().toLocaleTimeString(); }, 1000);
loadProjects().catch(error => toast(error.message));
