import { loadState, saveState, resetState } from './store.js?v=2';
import { curriculum, interestCopy, routineOptions } from './data.js?v=2';
import { getWeather } from './weather.js';
import { createGame, initGrade } from './tools.js';

let state = loadState();
let latestWeather = state.weatherCache;
const $ = selector => document.querySelector(selector);
const $$ = selector => [...document.querySelectorAll(selector)];
const WEATHER_CACHE_MAX_AGE = 60 * 60 * 1000;

if ('scrollRestoration' in history) history.scrollRestoration = 'manual';

function persist() { saveState(state); }

function localDateKey(date = new Date()) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

function getDailyRecord(key = localDateKey()) {
  if (!state.dailyRecords) state.dailyRecords = {};
  if (!state.dailyRecords[key]) {
    state.dailyRecords[key] = { completedGoalIds: [], selectedClass: '', routineCreated: false, bagPrepared: false };
  }
  return state.dailyRecords[key];
}

function dailyScore(record = {}, dateKey = '') {
  const scheduleChecked = dateKey
    ? record.selectedClass?.startsWith(`${dateKey} `)
    : Boolean(record.selectedClass);
  const completed = [
    Boolean(record.completedGoalIds?.length),
    Boolean(scheduleChecked),
    Boolean(record.routineCreated),
    Boolean(record.bagPrepared)
  ].filter(Boolean).length;
  return Math.round(completed / 4 * 100);
}

function recordDaily(patch) {
  Object.assign(getDailyRecord(), patch, { updatedAt: Date.now() });
  persist();
  renderDailyInsights();
}

function scrollToTop() {
  window.scrollTo({ top: 0, left: 0, behavior: 'auto' });
}

function route(viewName = location.hash.slice(1) || 'dashboard') {
  const target = document.getElementById(viewName) ? viewName : 'dashboard';
  $$('.view').forEach(view => view.classList.toggle('active', view.id === target));
  $$('.nav-link').forEach(link => {
    const isActive = link.dataset.view === target;
    link.classList.toggle('active', isActive);
    if (isActive) link.setAttribute('aria-current', 'page');
    else link.removeAttribute('aria-current');
  });
  if (location.hash !== `#${target}`) history.replaceState(null, '', `#${target}`);
  scrollToTop();
}

function setupNavigation() {
  window.addEventListener('hashchange', () => route());
  $$('[data-route]').forEach(link => link.addEventListener('click', event => { event.preventDefault(); location.hash = link.dataset.route; }));
  route();
}

function parseLocalDate(key) {
  const [year, month, day] = key.split('-').map(Number);
  return new Date(year, month - 1, day);
}

function formatScheduleDate(key, options = { month: 'long', day: 'numeric', weekday: 'short' }) {
  return new Intl.DateTimeFormat('ko-KR', options).format(parseLocalDate(key));
}

function scheduleItemOn(key = localDateKey()) {
  return curriculum.find(item => item.date === key) || null;
}

function nextClassAfter(key = localDateKey()) {
  return curriculum.find(item => item.kind === 'class' && item.date > key) || null;
}

function currentClass() {
  const todayKey = localDateKey();
  const today = scheduleItemOn(todayKey);
  const next = nextClassAfter(todayKey);
  if (today) {
    return {
      name: today.title,
      time: today.kind === 'holiday'
        ? `${formatScheduleDate(today.date)} · 수업 없음`
        : `${today.week}주차 · ${today.note || formatScheduleDate(today.date)}`
    };
  }
  if (next) return { name: '수업 없는 날', time: `다음 일정 · ${formatScheduleDate(next.date)} ${next.title}` };
  return { name: '교육과정이 종료되었습니다', time: '2026년 12월 11일 수료' };
}

function renderHeader() {
  const now = new Date();
  $('#today-label').textContent = new Intl.DateTimeFormat('ko-KR', { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' }).format(now);
  $('#user-name').textContent = state.profile.name;
  $('#welcome-copy').textContent = state.profile.intro || '작은 목표부터 차근차근 시작해 보세요.';
  const current = currentClass();
  $('#current-class').textContent = current.name;
  $('#class-time').textContent = current.time;
  const options = interestCopy[state.profile.interest] || interestCopy.frontend;
  $('#focus-title').textContent = `${state.profile.name}님을 위한 오늘의 추천`;
  $('#focus-copy').textContent = options[new Date().getDate() % options.length];
}

function renderGoals() {
  const list = $('#goal-list'); list.innerHTML = '';
  state.goals.forEach(goal => {
    const li = document.createElement('li');
    li.className = 'goal-item';
    const label = document.createElement('label');
    label.className = 'goal-check';
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.checked = goal.done;
    checkbox.setAttribute('aria-label', `${goal.text} 완료`);
    const copy = document.createElement('span');
    copy.className = 'goal-copy';
    const title = document.createElement('strong');
    title.textContent = goal.text;
    const meta = document.createElement('small');
    const priorities = { high: '중요', normal: '보통', low: '낮음' };
    meta.textContent = [priorities[goal.priority || 'normal'], goal.dueDate ? `목표일 ${goal.dueDate}` : '목표일 없음'].join(' · ');
    copy.append(title, meta);
    label.append(checkbox, copy);

    const actions = document.createElement('div');
    actions.className = 'goal-actions';
    const edit = document.createElement('button');
    edit.className = 'goal-edit';
    edit.type = 'button';
    edit.textContent = '수정';
    edit.setAttribute('aria-label', `${goal.text} 수정`);
    const remove = document.createElement('button');
    remove.className = 'goal-remove';
    remove.type = 'button';
    remove.textContent = '✕';
    remove.setAttribute('aria-label', `${goal.text} 삭제`);
    actions.append(edit, remove);
    li.append(label, actions);

    checkbox.addEventListener('change', event => {
      goal.done = event.target.checked;
      const completedGoalIds = new Set(getDailyRecord().completedGoalIds || []);
      if (goal.done) completedGoalIds.add(goal.id);
      else completedGoalIds.delete(goal.id);
      recordDaily({ completedGoalIds: [...completedGoalIds] });
      renderGoals();
    });
    edit.addEventListener('click', () => openGoalEditor(goal));
    remove.addEventListener('click', () => {
      state.goals = state.goals.filter(item => item.id !== goal.id);
      const record = getDailyRecord();
      record.completedGoalIds = (record.completedGoalIds || []).filter(id => id !== goal.id);
      persist();
      renderGoals();
      renderDailyInsights();
    });
    list.append(li);
  });
  const done = state.goals.filter(goal => goal.done).length;
  const percent = state.goals.length ? Math.round(done / state.goals.length * 100) : 0;
  $('#goal-percent').textContent = `${percent}%`;
  $('#goal-progress').style.width = `${percent}%`;
}

function openGoalEditor(goal = null) {
  $('#goal-dialog-title').textContent = goal ? '목표 수정' : '목표 추가';
  $('#goal-id').value = goal?.id || '';
  $('#goal-text').value = goal?.text || '';
  $('#goal-priority').value = goal?.priority || 'normal';
  $('#goal-due').value = goal?.dueDate || '';
  $('#goal-dialog').showModal();
  $('#goal-text').focus();
}

function setupGoals() {
  const dialog = $('#goal-dialog');
  const close = () => dialog.close();
  $('#add-goal').addEventListener('click', () => openGoalEditor());
  $('#close-goal-dialog').addEventListener('click', close);
  $('#cancel-goal').addEventListener('click', close);
  $('#goal-form').addEventListener('submit', event => {
    event.preventDefault();
    const text = $('#goal-text').value.trim();
    if (!text) return;
    const id = $('#goal-id').value;
    const existing = state.goals.find(goal => goal.id === id);
    const values = { text: text.slice(0, 40), priority: $('#goal-priority').value, dueDate: $('#goal-due').value };
    if (existing) Object.assign(existing, values);
    else state.goals.push({ id: `goal-${Date.now()}`, ...values, done: false });
    persist();
    renderGoals();
    close();
  });
}

const scheduleStart = parseLocalDate('2026-07-14');
const scheduleEnd = parseLocalDate('2026-12-11');

function clampScheduleDate(date) {
  return new Date(Math.min(scheduleEnd.getTime(), Math.max(scheduleStart.getTime(), date.getTime())));
}

let scheduleCursor = clampScheduleDate(parseLocalDate(localDateKey()));
let selectedScheduleDate = '';

function mondayOf(date) {
  const monday = new Date(date);
  const day = monday.getDay();
  monday.setDate(monday.getDate() - (day === 0 ? 6 : day - 1));
  monday.setHours(0, 0, 0, 0);
  return monday;
}

function moveSchedule(days) {
  const target = new Date(scheduleCursor);
  target.setDate(target.getDate() + days);
  scheduleCursor = clampScheduleDate(target);
  renderSchedule();
}

function renderSchedule() {
  const weekStart = mondayOf(scheduleCursor);
  const weekEnd = new Date(weekStart);
  weekEnd.setDate(weekEnd.getDate() + 6);
  const keyFor = date => localDateKey(date);
  const formatRange = new Intl.DateTimeFormat('ko-KR', { year: 'numeric', month: 'long', day: 'numeric' });
  $('#schedule-range').textContent = `${formatRange.format(weekStart)} — ${formatRange.format(weekEnd)}`;
  $('#schedule-date').value = keyFor(scheduleCursor);
  $('#schedule-prev').disabled = weekStart <= mondayOf(scheduleStart);
  $('#schedule-next').disabled = weekStart >= mondayOf(scheduleEnd);

  const container = $('#week-schedule');
  container.replaceChildren();
  const weekdays = ['일', '월', '화', '수', '목', '금', '토'];
  for (let offset = 0; offset < 7; offset += 1) {
    const date = new Date(weekStart);
    date.setDate(date.getDate() + offset);
    const key = keyFor(date);
    const item = scheduleItemOn(key);
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'schedule-day';
    button.dataset.date = key;
    button.classList.toggle('today', key === localDateKey());
    button.classList.toggle('selected', key === selectedScheduleDate);
    button.classList.toggle('holiday', item?.kind === 'holiday');
    button.classList.toggle('empty', !item);
    button.setAttribute('aria-pressed', String(key === selectedScheduleDate));
    button.setAttribute('aria-label', `${formatScheduleDate(key)} ${item?.title || '수업 없음'} 선택`);

    const dateBox = document.createElement('span');
    dateBox.className = 'schedule-day-date';
    dateBox.innerHTML = `<b>${date.getDate()}</b><small>${weekdays[date.getDay()]}</small>`;
    const content = document.createElement('span');
    content.className = 'schedule-day-content';
    const badge = document.createElement('small');
    badge.textContent = item?.kind === 'holiday' ? '휴강 · 휴일' : item?.week ? `${item.week}주차` : 'NO CLASS';
    const title = document.createElement('strong');
    title.textContent = item?.title || '수업 없음';
    const note = document.createElement('span');
    note.textContent = item?.note || (item?.kind === 'class' ? '정규 교육일정' : '개인 일정과 복습을 계획해 보세요.');
    content.append(badge, title, note);
    button.append(dateBox, content);
    button.addEventListener('click', () => selectClass(button, item));
    container.append(button);
  }
}

function selectClass(button, item) {
  selectedScheduleDate = button.dataset.date;
  $$('.schedule-day').forEach(day => {
    day.classList.toggle('selected', day === button);
    day.setAttribute('aria-pressed', String(day === button));
  });
  $('#selected-class').textContent = item?.title || '수업 없는 날';
  const meta = [formatScheduleDate(selectedScheduleDate), item?.week ? `${item.week}주차` : '', item?.note || ''].filter(Boolean);
  $('#selected-class-time').textContent = meta.join(' · ');
  if (selectedScheduleDate === localDateKey()) {
    recordDaily({ selectedClass: `${selectedScheduleDate} ${item?.title || '수업 없음'}` });
  }
  if (!item || item.kind === 'holiday') {
    $('#class-checks').innerHTML = '<p class="muted">정규 수업이 없는 날입니다. 다음 수업을 미리 준비하거나 밀린 복습을 해보세요.</p>';
    return;
  }
  const key = selectedScheduleDate;
  const checks = state.classChecks[key] || { prepare: false, review: false, note: false };
  const labels = { prepare: '준비물과 자료 확인', review: '핵심 내용 복습', note: '배운 점 한 줄 기록' };
  const box = $('#class-checks'); box.innerHTML = '';
  Object.entries(labels).forEach(([id, text]) => {
    const label = document.createElement('label'); label.innerHTML = `<input type="checkbox" ${checks[id] ? 'checked' : ''}><span>${text}</span>`;
    label.querySelector('input').addEventListener('change', event => { checks[id] = event.target.checked; state.classChecks[key] = checks; persist(); }); box.append(label);
  });
}

function setupSchedule() {
  $('#schedule-prev').addEventListener('click', () => moveSchedule(-7));
  $('#schedule-next').addEventListener('click', () => moveSchedule(7));
  $('#schedule-today').addEventListener('click', () => {
    scheduleCursor = clampScheduleDate(parseLocalDate(localDateKey()));
    renderSchedule();
  });
  $('#schedule-date').addEventListener('change', event => {
    if (!event.target.value) return;
    scheduleCursor = parseLocalDate(event.target.value);
    renderSchedule();
  });
}

function renderRoutine(routine) {
  if (!routine || !routineOptions[routine.mood]) return;
  $('#mood').value = routine.mood;
  $('#available-time').value = String(routine.hours);
  $('#routine-priority').value = routine.priority;

  const mood = routineOptions[routine.mood];
  const study = routine.priority === 'study' ? '관심 분야 집중 학습과 결과물 정리' : '오늘 배운 내용 30분 복습';
  const rest = routine.priority === 'rest' ? `${mood.rest} (충분히)` : mood.rest;
  const health = routine.priority === 'health' ? `${mood.health} (오늘의 중심 활동)` : mood.health;
  const items = routine.hours <= 2
    ? [['START', routine.priority === 'rest' ? rest : study], ['+ 60분', routine.priority === 'health' ? health : rest]]
    : [['10:00', health], ['12:00', '좋아하는 메뉴로 든든하게 식사하기'], ['14:00', study], [routine.hours >= 6 ? '17:00' : '16:00', rest]];
  $('#routine-list').innerHTML = items.map(([time, title], index) => `<li><time>${time}</time><div><strong>${title}</strong><p>${index === 0 ? mood.title : '다음 활동 전 10분의 여유를 두세요.'}</p></div></li>`).join('');
}

function setupRoutine() {
  renderRoutine(state.routine);
  $('#routine-form').addEventListener('submit', event => {
    event.preventDefault();
    state.routine = {
      mood: $('#mood').value,
      hours: Number($('#available-time').value),
      priority: $('#routine-priority').value
    };
    renderRoutine(state.routine);
    persist();
    recordDaily({ routineCreated: true });
  });
}

function setupTravel() {
  $$('.trip-card').forEach(card => {
    const button = card.querySelector('.favorite'), id = card.dataset.trip;
    const render = () => { const active = state.favorites.includes(id); button.classList.toggle('active', active); button.textContent = active ? '♥' : '♡'; button.setAttribute('aria-pressed', active); };
    button.addEventListener('click', () => { state.favorites = state.favorites.includes(id) ? state.favorites.filter(item => item !== id) : [...state.favorites, id]; persist(); render(); }); render();
  });
  $('#budget-form').addEventListener('submit', event => {
    event.preventDefault(); const daily = Number($('#budget-trip').value), days = Number($('#trip-days').value), people = Number($('#travelers').value);
    if (days < 1 || days > 30 || people < 1 || people > 10) { $('#budget-result').textContent = '일수와 인원을 올바르게 입력하세요.'; return; }
    const total = daily * days * people + 1200000 * people;
    $('#budget-result').textContent = `항공권 포함 약 ${total.toLocaleString('ko-KR')}원`;
  });
}

function renderBag() {
  const activity = $('#activity').value;
  const base = ['스마트폰', '지갑', '이어폰'];
  const byActivity = { class: ['노트북', '필기구'], study: ['노트북', '충전기'], trip: ['보조배터리', '물'] };
  const items = [...base, ...byActivity[activity], ...(latestWeather?.rain ? ['우산'] : []), ...(latestWeather?.temperature_2m > 27 ? ['물'] : [])];
  const unique = [...new Set(items)], box = $('#bag-list'); box.innerHTML = '';
  unique.forEach(item => {
    const label = document.createElement('label');
    label.innerHTML = `<input type="checkbox" ${state.bagChecks[item] ? 'checked' : ''}><span>${item}</span>`;
    label.querySelector('input').addEventListener('change', event => {
      state.bagChecks[item] = event.target.checked;
      recordDaily({ bagPrepared: Object.values(state.bagChecks).some(Boolean) });
    });
    box.append(label);
  });
  $('#bag-advice').textContent = latestWeather?.rain ? '비 소식이 있어 우산을 추가했어요.' : '오늘 활동에 필요한 기본 준비물입니다.';
}

async function refreshWeather() {
  $('#weather-retry').hidden = true; $('#weather-advice').textContent = '날씨를 불러오는 중입니다';
  try { latestWeather = await getWeather(); state.weatherCache = latestWeather; persist(); showWeather(false); }
  catch {
    const cacheIsFresh = state.weatherCache?.fetchedAt && Date.now() - state.weatherCache.fetchedAt < WEATHER_CACHE_MAX_AGE;
    if (cacheIsFresh) {
      latestWeather = state.weatherCache;
      showWeather(true);
    } else {
      latestWeather = null;
      $('#weather-temp').textContent = '--℃';
      $('#weather-advice').textContent = '날씨를 불러오지 못했습니다.';
      $('#weather-retry').hidden = false;
    }
  }
  renderBag();
}

function showWeather(cached) { $('#weather-temp').textContent = `${Math.round(latestWeather.temperature_2m)}℃`; $('#weather-advice').textContent = `${latestWeather.text}${cached ? ' · 저장된 정보' : ''}`; }

function renderDailyInsights() {
  const record = getDailyRecord();
  const todayKey = localDateKey();
  const scheduleChecked = record.selectedClass?.startsWith(`${todayKey} `);
  const items = [
    { label: '목표 하나 완료하기', done: Boolean(record.completedGoalIds?.length), route: 'dashboard' },
    { label: scheduleChecked ? record.selectedClass.slice(todayKey.length + 1) : '오늘 일정 확인하기', done: Boolean(scheduleChecked), route: 'schedule' },
    { label: '컨디션에 맞는 루틴 만들기', done: Boolean(record.routineCreated), route: 'routine' },
    { label: '오늘의 가방 준비하기', done: Boolean(record.bagPrepared), route: 'tools' }
  ];
  const score = dailyScore(record, todayKey);
  $('#daily-progress').textContent = `${score}%`;
  $('#daily-progress-bar').style.width = `${score}%`;
  const checklist = $('#daily-checklist');
  checklist.replaceChildren();
  items.forEach(item => {
    const li = document.createElement('li');
    li.classList.toggle('done', item.done);
    const mark = document.createElement('span');
    mark.setAttribute('aria-hidden', 'true');
    mark.textContent = item.done ? '✓' : '○';
    const link = document.createElement('a');
    link.href = `#${item.route}`;
    link.textContent = item.label;
    li.append(mark, link);
    checklist.append(li);
  });

  const chart = $('#weekly-chart');
  chart.replaceChildren();
  const scores = [];
  for (let offset = 6; offset >= 0; offset -= 1) {
    const date = new Date();
    date.setDate(date.getDate() - offset);
    const key = localDateKey(date);
    const value = dailyScore(state.dailyRecords?.[key], key);
    scores.push(value);
    const day = document.createElement('div');
    day.className = 'weekly-day';
    const bar = document.createElement('i');
    bar.style.height = `${Math.max(value, 4)}%`;
    bar.title = `${value}%`;
    const label = document.createElement('span');
    label.textContent = new Intl.DateTimeFormat('ko-KR', { weekday: 'short' }).format(date);
    const amount = document.createElement('small');
    amount.textContent = `${value}%`;
    day.append(amount, bar, label);
    chart.append(day);
  }
  const average = Math.round(scores.reduce((sum, value) => sum + value, 0) / scores.length);
  $('#weekly-average').textContent = `평균 ${average}%`;
}

function setupSettings() {
  const dialog = $('#settings-dialog');
  const interestNames = { frontend: '프론트엔드', design: 'UI/UX', security: '정보보안', cloud: '클라우드' };
  function updateSummary() {
    const name = $('#setting-name').value.trim() || '이름 미입력';
    const interest = interestNames[$('#setting-interest').value];
    const intro = $('#setting-intro').value.trim() || '한 줄 소개 미입력';
    const summary = $('#settings-summary');
    const heading = document.createElement('strong');
    heading.textContent = `${name} · ${interest}`;
    const description = document.createElement('span');
    description.textContent = intro;
    summary.replaceChildren(heading, document.createElement('br'), description);
    summary.hidden = false;
  }
  function open() { $('#setting-name').value = state.profile.name; $('#setting-interest').value = state.profile.interest; $('#setting-intro').value = state.profile.intro; updateSummary(); dialog.showModal(); }
  $('#open-settings').addEventListener('click', open); $('#close-settings').addEventListener('click', () => dialog.close());
  ['#setting-name', '#setting-interest', '#setting-intro'].forEach(selector => $(selector).addEventListener('input', updateSummary));
  $('#settings-form').addEventListener('submit', event => { event.preventDefault(); const name = $('#setting-name').value.trim(); if (!name) return; state.profile = { name, interest: $('#setting-interest').value, intro: $('#setting-intro').value.trim() }; state.configured = true; persist(); renderHeader(); dialog.close(); });
  $('#reset-data').addEventListener('click', () => { if (!confirm('저장된 목표와 설정을 모두 초기화할까요?')) return; resetState(); location.reload(); });
}

function init() {
  scrollToTop();
  window.addEventListener('pageshow', scrollToTop, { once: true });
  setupNavigation(); renderHeader(); renderGoals(); setupGoals(); renderSchedule(); setupSchedule(); setupRoutine(); setupTravel(); renderDailyInsights();
  createGame(state.gameBest, best => { state.gameBest = best; persist(); }); initGrade();
  $('#activity').addEventListener('change', renderBag); $('#weather-retry').addEventListener('click', refreshWeather);
  if (latestWeather) showWeather(true); renderBag(); refreshWeather(); setupSettings();
}

init();
