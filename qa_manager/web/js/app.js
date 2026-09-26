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
function coversCategory(run, category) {
  return run.suite === category || run.suite === 'all' || (category === 'security' && ['zap', 'trivy'].includes(run.suite));
}
function resultCounts(summary) {
  return ['PASS', 'FAIL', 'WARNING', 'ERROR', 'SKIPPED'].map(status => `${summary[status] || 0} ${status}`).join(' · ');
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
  testsProjectId = active?.id || null;
  $('#empty').hidden = !!active; $('#dashboard').hidden = !active;
  $('#runAll').disabled = !active || !active.enabled; $('#runDetail').hidden = true;
  $('#overall').className = 'status neutral'; $('#overall b').textContent = 'NOT RUN';
  categories.forEach(category => { $('#' + category + 'Metric').textContent = 'NOT RUN'; });
  $('#runs').replaceChildren(); $('#testSummary').textContent = '';
  $('#regressionMetric').textContent = 'NOT RUN';
  $('#zapResult').textContent = 'NOT RUN'; $('#trivyResult').textContent = 'NOT RUN';
  if (!active) return;
  $('#projectName').textContent = active.name;
  $('#projectUrl').textContent = active.frontend_url; $('#projectUrl').href = active.frontend_url;
  $$('[data-run]').forEach(button => { button.disabled = !active.enabled; });
  $('#activeZap').disabled = !active.enabled;
  $('#testsError').textContent = '';
  $('#apiForm').reset(); $('#scenarioForm').reset();
  $('#apiForm').elements.url.value = (active.backend_urls?.[0] || active.backend_url || active.frontend_url) + '/';
  setPreparationTab('system', false);
  await Promise.all([loadRuns(), refreshTests(), loadSecurity()]);
}
function setPreparationTab(name, focus = true) {
  for (const tab of $$('[data-prep-tab]')) {
    const selected = tab.dataset.prepTab === name;
    tab.setAttribute('aria-selected', String(selected));
    tab.tabIndex = selected ? 0 : -1;
    $('#' + tab.getAttribute('aria-controls')).hidden = !selected;
  }
  if (focus) $('#prepTab' + name[0].toUpperCase() + name.slice(1)).focus();
}
$$('[data-prep-tab]').forEach(tab => {
  tab.onclick = () => setPreparationTab(tab.dataset.prepTab, false);
  tab.onkeydown = event => {
    const tabs = [...$$('[data-prep-tab]')], index = tabs.indexOf(tab);
    const next = event.key === 'ArrowRight' ? (index + 1) % tabs.length : event.key === 'ArrowLeft' ? (index - 1 + tabs.length) % tabs.length : -1;
    if (next >= 0) { event.preventDefault(); setPreparationTab(tabs[next].dataset.prepTab); }
  };
});
async function loadRuns() {
  clearTimeout(poll);
  if (!active) return;
  const id = active.id, currentGeneration = generation, version = ++refreshVersion;
  const current = () => active?.id === id && generation === currentGeneration && refreshVersion === version;
  try {
    const runs = await api(`/projects/${id}/runs`);
    const relevant = categories.map(category => runs.find(run => coversCategory(run, category))).filter(Boolean);
    for (const scanner of ['zap', 'trivy']) {
      const latest = runs.find(run => ['all', 'security', scanner].includes(run.suite));
      if (latest) relevant.push(latest);
    }
    const details = await Promise.all([...new Set(relevant.map(run => run.id))].map(runId => api(`/runs/${runId}`)));
    if (!current()) return;
    const box = $('#runs'); box.replaceChildren();
    if (!runs.length) box.append(node('p', '아직 실행 이력이 없습니다. 기본 테스트를 추가한 뒤 System Check부터 실행하세요.', 'muted'));
    runs.slice(0, 20).forEach(run => {
      const row = node('div', null, 'run'), button = node('button', run.suite.toUpperCase() + ' 상세');
      button.onclick = () => showRun(run.id).catch(error => toast(error.message));
      const elapsed = run.duration_ms == null ? Math.max(0, Date.now() - new Date(run.started_at)) : run.duration_ms;
      row.append(badge(run.status), button, node('span', new Date(run.started_at).toLocaleString() + (run.current_stage ? ' · ' + run.current_stage : '')), node('span', (elapsed / 1000).toFixed(1) + 's'));
      if (run.suite === 'regression') row.append(node('span', resultCounts(run.summary || {})));
      box.append(row);
    });
    $('#overall').className = 'status ' + (runs[0]?.status || 'neutral');
    $('#overall b').textContent = runs[0]?.status || 'NOT RUN';
    const regression = runs.find(run => run.suite === 'regression');
    $('#regressionMetric').textContent = regression ? `${regression.status} · ${resultCounts(regression.summary || {})}` : 'NOT RUN';
    for (const scanner of ['zap', 'trivy']) {
      const summary = runs.find(run => ['all', 'security', scanner].includes(run.suite));
      const detail = details.find(run => run.id === summary?.id);
      const finding = detail?.results?.find(result => result.details?.scanner === scanner);
      $('#' + scanner + 'Result').textContent = finding ? `${finding.status} · ${finding.message || ''}` : 'NOT RUN';
      if (scanner === 'trivy' && finding?.details?.summary) {
        $('#trivyResult').textContent += '\n' + Object.entries(finding.details.summary).map(([severity, count]) => `${severity} ${count}`).join(' · ');
      }
    }
    categories.forEach(category => {
      const summary = runs.find(run => coversCategory(run, category));
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
  if (run.suite === 'regression') {
    const summary = {}; run.results.forEach(result => { summary[result.status] = (summary[result.status] || 0) + 1; });
    box.append(node('p', resultCounts(summary)));
  }
  if (run.results.some(result => ['api', 'e2e'].includes(result.category) && ['FAIL', 'ERROR'].includes(result.status) && result.source_id)) {
    const retry = node('button', run.suite === 'regression' ? '↻ Retry Failed' : '↻ 실패한 API/E2E 항목만 다시 실행', 'primary');
    retry.disabled = ['RUNNING', 'QUEUED'].includes(run.status);
    retry.onclick = async () => {
      retry.disabled = true;
      try { await api(`/runs/${run.id}/retry-failed`, {method: 'POST', body: '{}'}); toast('실패 항목 재실행을 예약했습니다.'); await loadRuns(); }
      catch (error) { toast(error.message); retry.disabled = false; }
    };
    box.append(retry);
  }
  for (const result of run.results) {
    const item = node('article', null, 'result');
    item.append(badge(result.status), node('h3', result.category.toUpperCase() + ' · ' + result.test_name), node('p', result.message));
    item.append(node('p', `${result.duration_ms}ms`));
    if (result.category === 'e2e' && result.source_id && ['FAIL', 'ERROR'].includes(result.status)) {
      const retry = node('button', 'Retry Scenario');
      retry.disabled = ['RUNNING', 'QUEUED'].includes(run.status);
      retry.onclick = async () => {
        retry.disabled = true;
        try { await api(`/runs/${run.id}/retry-failed`, {method: 'POST', body: JSON.stringify({scenario_id: result.source_id})}); await loadRuns(); toast('시나리오 재실행을 예약했습니다.'); }
        catch (error) { toast(error.message); retry.disabled = false; }
      };
      item.append(retry);
    }
    if (result.details?.scanner === 'trivy' && result.details.summary) renderTrivyResult(item, result.details);
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
$('#clearHistory').onclick = async () => {
  if (!active) return;
  const project = active, button = $('#clearHistory');
  if (!confirm(`${project.name}의 완료된 실행 이력과 결과를 모두 삭제할까요? 실행·대기 중인 작업과 등록된 테스트는 유지됩니다. 증거 파일은 디스크에 남습니다.`)) return;
  button.disabled = true;
  try {
    const result = await api(`/projects/${project.id}/runs`, {method: 'DELETE'});
    if (active?.id === project.id) {
      refreshVersion++; detailVersion++; clearTimeout(poll);
      $('#runDetail').hidden = true; $('#runDetail').replaceChildren();
      await loadRuns();
    }
    toast(`${project.name}: 실행 이력 ${result.deleted}개를 삭제했습니다.`);
  } catch (error) { toast(error.message); }
  finally { button.disabled = false; }
};
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
    $('#trivyExecutable').value = settings.trivy_executable || '';
  } catch (error) { $('#setupError').textContent = error.message; }
  await checkReadiness();
};
$('#checkReadiness').onclick = checkReadiness;
$('#saveSettings').onclick = async () => {
  try {
    await api('/settings', {method: 'PUT', body: JSON.stringify({zap_api_url: $('#zapUrl').value, security_enabled: $('#securityEnabled').checked, trivy_executable: $('#trivyExecutable').value.trim()})});
    $('#setupError').textContent = ''; toast('설정 저장 완료');
  } catch (error) { $('#setupError').textContent = error.message; }
};
async function refreshTests() {
  const id = testsProjectId;
  if (!id) return;
  const [cases, scenarios] = await Promise.all([api(`/projects/${id}/api-tests`), api(`/projects/${id}/scenarios`)]);
  if (id !== testsProjectId) return;
  for (const [label, items, endpoint] of [['API', cases, 'api-tests'], ['E2E', scenarios, 'scenarios']]) {
    const list = $(label === 'API' ? '#apiTestList' : '#scenarioTestList'); list.replaceChildren();
    const heading = node('h3', `등록된 ${label} · ${items.length}`);
    list.append(heading);
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
  if (active?.id === id) await Promise.all([loadPreparation(), loadRegression(), loadTestSummary()]);
}
$('#exportRecipe').onclick = async () => {
  if (!testsProjectId) return;
  try {
    const response = await fetch(`/api/projects/${testsProjectId}/recipe`);
    if (!response.ok) throw Error((await response.json()).detail || response.statusText);
    const link = document.createElement('a');
    link.href = URL.createObjectURL(await response.blob());
    link.download = `${active?.name || 'project'}.qaroz.json`;
    link.click(); URL.revokeObjectURL(link.href); toast('JSON 작업 지시서를 저장했습니다.');
  } catch (error) { $('#testsError').textContent = error.message; }
};
$('#importRecipe').onclick = () => $('#recipeFile').click();
$('#recipeFile').onchange = async event => {
  const file = event.target.files[0];
  if (!file || !testsProjectId) return;
  try {
    const recipe = JSON.parse(await file.text());
    const result = await api(`/projects/${testsProjectId}/recipe`, {method: 'POST', body: JSON.stringify(recipe)});
    await refreshTests(); await loadTestSummary();
    toast(`작업 지시서에서 API ${result.api_tests}개, E2E ${result.scenarios}개를 추가했습니다.`);
    $('#testsError').textContent = '';
  } catch (error) { $('#testsError').textContent = `불러오기 실패: ${error.message}`; }
  finally { event.target.value = ''; }
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
    if (active?.id === project.id) await refreshTests(); toast('기본 연결 테스트 준비 완료. 업무 기능 검사는 별도 등록하세요.');
  } catch (error) { toast(error.message); }
  finally { $('#starter').disabled = false; }
};
setInterval(() => { $('#clock').textContent = new Date().toLocaleTimeString(); }, 1000);
loadProjects().catch(error => toast(error.message));

async function loadRegression() {
  if (!active) return;
  const id = active.id, currentGeneration = generation;
  const scenarios = await api(`/projects/${id}/scenarios`);
  if (active?.id !== id || generation !== currentGeneration) return;
  const list = $('#regressionList'); list.replaceChildren();
  const groups = new Map();
  scenarios.sort((a, b) => a.order - b.order).forEach(scenario => {
    const group = scenario.group || 'Ungrouped';
    if (!groups.has(group)) groups.set(group, []);
    groups.get(group).push(scenario);
  });
  if (!scenarios.length) list.append(node('p', '저장된 시나리오가 없습니다. Record Scenario로 추가하세요.', 'muted'));
  for (const [group, items] of groups) {
    list.append(node('h3', group));
    for (const scenario of items) {
      const row = node('div', null, 'regression-row');
      const label = node('label', null, 'check'), check = node('input');
      check.type = 'checkbox'; check.checked = scenario.regression_enabled; check.disabled = !scenario.enabled;
      label.append(check, node('span', scenario.name + (scenario.enabled ? '' : ' (비활성)')));
      const groupLabel = node('label', 'Group'), groupInput = node('input'); groupInput.value = scenario.group || ''; groupInput.maxLength = 200; groupLabel.append(groupInput);
      const orderLabel = node('label', 'Order'), orderInput = node('input'); orderInput.type = 'number'; orderInput.value = scenario.order; orderInput.step = '1'; orderLabel.append(orderInput);
      const save = node('button', '저장');
      const update = async payload => {
        try { await api(`/scenarios/${scenario.id}`, {method: 'PATCH', body: JSON.stringify(payload)}); if (active?.id === id) await loadRegression(); }
        catch (error) { toast(error.message); check.checked = scenario.regression_enabled; }
      };
      check.onchange = () => update({regression_enabled: check.checked});
      save.onclick = () => update({group: groupInput.value.trim() || null, order: Number(orderInput.value)});
      row.append(label, groupLabel, orderLabel, save); list.append(row);
    }
  }
}
async function loadPreparation() {
  if (!active) return;
  const project = active, id = project.id;
  const [cases, scenarios] = await Promise.all([
    api(`/projects/${id}/api-tests`), api(`/projects/${id}/scenarios`),
  ]);
  if (active?.id !== id) return;
  const system = $('#systemPreparation'); system.replaceChildren();
  system.append(node('p', `Frontend · ${project.frontend_url}`));
  system.append(node('p', `Backend · ${(project.backend_urls || []).join(', ') || '미등록'}`));
  system.append(node('p', `Health · ${(project.health_urls || []).join(', ') || 'Backend 기본 URL 검사'}`));
  system.append(node('p', `Ports · ${(project.expected_ports || []).join(', ') || '미등록'}　 Process · ${(project.process_rules || []).join(', ') || '미등록'}`));
  const apiList = $('#apiPreparationList'); apiList.replaceChildren();
  const enabledCases = cases.filter(item => item.enabled);
  apiList.append(node('p', `활성 ${enabledCases.length} / 전체 ${cases.length}`));
  if (enabledCases.length) apiList.append(node('p', enabledCases.map(item => `${item.method} ${item.name} · HTTP ${item.expected_status}`).join('　·　')));
  else apiList.append(node('p', 'API 테스트가 없습니다. 실제 서비스의 URL과 기대 응답을 등록하세요.', 'muted'));
  const e2eList = $('#e2ePreparationList'); e2eList.replaceChildren();
  const enabledScenarios = scenarios.filter(item => item.enabled);
  e2eList.append(node('p', `활성 ${enabledScenarios.length} / 전체 ${scenarios.length}`));
  if (enabledScenarios.length) e2eList.append(node('p', enabledScenarios.map(item => item.name).join('　·　')));
  else e2eList.append(node('p', 'E2E 시나리오가 없습니다. 직접 검증한 흐름을 녹화해 저장하세요.', 'muted'));
}
async function loadSecurity() {
  if (!active) return;
  const project = active;
  $('#projectZap').checked = !!project.zap_enabled;
  $('#projectTrivy').checked = !!project.trivy_enabled;
  $('#zapTarget').textContent = 'Target: ' + project.frontend_url;
  $('#trivyTarget').textContent = 'Target: ' + (project.project_path || '프로젝트 수정에서 Project path를 등록하세요.');
  $('#trivyStatus').textContent = '설치 상태 확인 버튼을 눌러 확인하세요.';
  $$('#trivyScanners input').forEach(input => { input.checked = (project.trivy_scanners || ['vuln', 'misconfig', 'secret']).includes(input.value); });
  if (project.zap_enabled == null) {
    const settings = await api('/settings');
    if (active?.id === project.id) $('#projectZap').checked = settings.security_enabled === 'true';
  }
}
$('#saveProjectSecurity').onclick = async () => {
  if (!active) return;
  const id = active.id;
  try {
    const project = await api(`/projects/${id}`, {method: 'PUT', body: JSON.stringify({
      zap_enabled: $('#projectZap').checked, trivy_enabled: $('#projectTrivy').checked,
      trivy_scanners: [...$$('#trivyScanners input')].filter(input => input.checked).map(input => input.value),
    })});
    projects = projects.map(item => item.id === id ? project : item);
    if (active?.id === id) active = project;
    toast('프로젝트 Security 설정을 저장했습니다.');
  } catch (error) { toast(error.message); }
};
$('#checkTrivy').onclick = async () => {
  const id = active?.id;
  $('#trivyStatus').textContent = '확인 중…';
  try {
    const status = await api('/system/trivy/status');
    if (active?.id === id) $('#trivyStatus').textContent = status.installed ? `Installed · Version: ${status.version}` : `Not Installed · ${status.message}`;
  } catch (error) { if (active?.id === id) $('#trivyStatus').textContent = error.message; }
};
$('#activeZap').onclick = async () => {
  if (!active || !active.enabled) return;
  const project = active;
  if (!confirm(`ZAP Active Scan은 공격 요청을 보냅니다. 대상: ${project.frontend_url}\n이 대상에 Active Scan을 실행할까요?`)) return;
  try { await api(`/projects/${project.id}/run/zap`, {method: 'POST', body: JSON.stringify({active: true})}); if (active?.id === project.id) await loadRuns(); }
  catch (error) { toast(error.message); }
};
$('#recordRegression').onclick = async () => {
  if (!active) return;
  testsProjectId = active.id;
  await $('#startRecorder').onclick();
};
function renderTrivyResult(container, report) {
  container.append(node('h3', Object.entries(report.summary).map(([severity, count]) => `${severity} ${count}`).join(' · ')));
  for (const category of ['Vulnerabilities', 'Misconfigurations', 'Secrets', 'Licenses']) {
    const findings = report.findings.filter(item => item.category === category);
    const section = node('details'); section.append(node('summary', `${category} · ${findings.length}`));
    if (category === 'Licenses') section.append(node('p', 'Trivy의 라이선스 이름과 분류이며 법적 판단이 아닙니다.'));
    for (const finding of findings) {
      const item = node('article', null, 'result');
      for (const [key, value] of Object.entries(finding)) if (key !== 'category') item.append(node('p', `${key}: ${typeof value === 'object' ? JSON.stringify(value) : value}`));
      section.append(item);
    }
    container.append(section);
  }
}

// Scenario Recorder is an adapter: its draft is converted to the unchanged
// {steps, expected} Scenario payload only when the user saves it.
let recorderId = null, recorderTimer = null, recorderDraft = {steps: [], expected: []};
function renderRecordedList(key) {
  const box = $(key === 'steps' ? '#recordedSteps' : '#recordedExpected'); box.replaceChildren();
  recorderDraft[key].forEach((item, index) => {
    const row = node('div', null, 'recorded-item');
    row.append(node('span', String(index + 1)), node('code', key === 'steps' ? item.action : item.type));
    const value = node('input'); value.value = JSON.stringify(item); value.setAttribute('aria-label', `${key} ${index + 1} JSON`);
    value.onchange = () => { try { recorderDraft[key][index] = JSON.parse(value.value); value.setCustomValidity(''); } catch (_) { value.setCustomValidity('유효한 JSON을 입력하세요.'); value.reportValidity(); } };
    const up = node('button', '↑'), down = node('button', '↓'), remove = node('button', '삭제');
    up.disabled = index === 0; down.disabled = index === recorderDraft[key].length - 1;
    up.onclick = () => { [recorderDraft[key][index - 1], recorderDraft[key][index]] = [item, recorderDraft[key][index - 1]]; renderRecordedList(key); };
    down.onclick = () => { [recorderDraft[key][index + 1], recorderDraft[key][index]] = [item, recorderDraft[key][index + 1]]; renderRecordedList(key); };
    remove.onclick = () => { recorderDraft[key].splice(index, 1); renderRecordedList(key); };
    row.append(value, up, down, remove); box.append(row);
  });
  if (!recorderDraft[key].length) box.append(node('p', '아직 기록이 없습니다.', 'muted'));
}
function renderRecording(recording) {
  recorderDraft = {steps: recording.steps || [], expected: recording.expected || []};
  $('#recorderStatus').textContent = `상태: ${recording.status}${recording.error ? ' · ' + recording.error : ''}`;
  $('#saveRecording').disabled = recording.status !== 'stopped';
  $('#stopRecorder').disabled = !['starting', 'recording'].includes(recording.status);
  renderRecordedList('steps'); renderRecordedList('expected');
}
async function pollRecording() {
  if (!recorderId) return;
  try {
    const recording = await api(`/recordings/${recorderId}`); renderRecording(recording);
    if (['starting', 'recording'].includes(recording.status)) recorderTimer = setTimeout(pollRecording, 500);
  } catch (error) { $('#recorderError').textContent = error.message; }
}
$('#startRecorder').onclick = async () => {
  if (!testsProjectId) return;
  clearTimeout(recorderTimer); $('#recorderError').textContent = ''; $('#recorderDialog').showModal();
  try {
    const recording = await api(`/projects/${testsProjectId}/recordings`, {method: 'POST', body: '{}'});
    recorderId = recording.id; renderRecording(recording); pollRecording();
  } catch (error) { $('#recorderError').textContent = error.message; }
};
$$('[data-verify]').forEach(button => { button.onclick = async () => {
  try { await api(`/recordings/${recorderId}/commands`, {method: 'POST', body: JSON.stringify({command: `verify_${button.dataset.verify}`})}); toast('대상 브라우저에서 검증할 요소를 클릭하세요.'); }
  catch (error) { $('#recorderError').textContent = error.message; }
}; });
$('#addWait').onclick = () => { $('#waitEditor').hidden = !$('#waitEditor').hidden; };
$('#saveWait').onclick = async () => {
  try {
    await api(`/recordings/${recorderId}/commands`, {method: 'POST', body: JSON.stringify({command: 'add_wait', selector: $('#waitSelector').value, state: $('#waitState').value, timeout: Number($('#waitTimeout').value)})});
    $('#waitEditor').hidden = true; await pollRecording();
  } catch (error) { $('#recorderError').textContent = error.message; }
};
$('#stopRecorder').onclick = async () => {
  try { await api(`/recordings/${recorderId}/commands`, {method: 'POST', body: JSON.stringify({command: 'stop'})}); clearTimeout(recorderTimer); setTimeout(pollRecording, 300); }
  catch (error) { $('#recorderError').textContent = error.message; }
};
$('#saveRecording').onclick = async () => {
  try {
    if (!recorderDraft.steps.length || !recorderDraft.expected.length) throw Error('Step과 Expected가 각각 하나 이상 필요합니다.');
    await api(`/projects/${testsProjectId}/scenarios`, {method: 'POST', body: JSON.stringify({name: $('#recordedName').value, steps: recorderDraft.steps, expected: recorderDraft.expected})});
    $('#recorderDialog').close(); await refreshTests(); await loadTestSummary(); toast('녹화 시나리오 저장 완료');
  } catch (error) { $('#recorderError').textContent = error.message; }
};
$('#recorderDialog').onclose = () => {
  clearTimeout(recorderTimer);
  if (recorderId && !$('#stopRecorder').disabled) api(`/recordings/${recorderId}/commands`, {method: 'POST', body: JSON.stringify({command: 'stop'})}).catch(() => {});
};
