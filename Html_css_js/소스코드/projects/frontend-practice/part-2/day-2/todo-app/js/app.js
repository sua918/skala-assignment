import { loadTodos, saveTodos } from './storage.js?v=2';

const form = document.querySelector('#todoForm');
const input = document.querySelector('#todoInput');
const priorityInput = document.querySelector('#priorityInput');
const dueDateInput = document.querySelector('#dueDateInput');
const submitButton = document.querySelector('#submitButton');
const cancelEditButton = document.querySelector('#cancelEditButton');
const list = document.querySelector('#todoList');
const filters = document.querySelector('#filters');
const summary = document.querySelector('#summary');
const emptyState = document.querySelector('#emptyState');
const progressText = document.querySelector('#progressText');
const progressBar = document.querySelector('#progressBar');
const todoFeedback = document.querySelector('#todoFeedback');
let todos = loadTodos();
let currentFilter = 'all';
let editingId = null;

function filteredTodos() {
  if (currentFilter === 'active') return todos.filter(todo => !todo.done);
  if (currentFilter === 'done') return todos.filter(todo => todo.done);
  return todos;
}

function render() {
  list.replaceChildren();
  for (const todo of filteredTodos()) {
    const item = document.createElement('li');
    item.dataset.id = todo.id;
    item.classList.toggle('done', todo.done);
    item.classList.toggle('overdue', isOverdue(todo));
    item.innerHTML = `
      <input class="toggle" type="checkbox" ${todo.done ? 'checked' : ''}>
      <div class="todo-content">
        <span class="todo-text"></span>
        <small class="todo-meta"></small>
      </div>
      <button class="edit" type="button">수정</button>
      <button class="delete" type="button">✕</button>
    `;
    item.querySelector('.todo-text').textContent = todo.text;
    item.querySelector('.todo-meta').textContent = formatMeta(todo);
    item.querySelector('.toggle').setAttribute('aria-label', `${todo.text} 완료 상태 변경`);
    item.querySelector('.edit').setAttribute('aria-label', `${todo.text} 수정`);
    item.querySelector('.delete').setAttribute('aria-label', `${todo.text} 삭제`);
    list.append(item);
  }
  const completed = todos.filter(todo => todo.done).length;
  const progress = todos.length ? Math.round((completed / todos.length) * 100) : 0;
  summary.textContent = `전체 ${todos.length}개 · 완료 ${completed}개 · 남은 할 일 ${todos.length - completed}개`;
  progressText.textContent = `${progress}%`;
  progressBar.style.width = `${progress}%`;
  emptyState.hidden = filteredTodos().length !== 0;
  saveTodos(todos);
}

function isOverdue(todo) {
  if (!todo.dueDate || todo.done) return false;
  const now = new Date();
  const localToday = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
  return todo.dueDate < localToday;
}

function formatMeta(todo) {
  const priorityLabels = { high: '중요', normal: '보통', low: '낮음' };
  const parts = [`중요도 ${priorityLabels[todo.priority] || '보통'}`];
  if (todo.dueDate) parts.push(`${isOverdue(todo) ? '기한 지남' : '마감'} ${todo.dueDate}`);
  return parts.join(' · ');
}

function updateDueDate() {
  let message = '';
  if (dueDateInput.value && dueDateInput.value < dueDateInput.min) {
    message = '마감일은 1900년 이후로 선택해 주세요.';
  } else if (dueDateInput.value && dueDateInput.value > dueDateInput.max) {
    message = '마감일 연도는 4자리로 선택해 주세요.';
  }

  dueDateInput.setCustomValidity(message);
  dueDateInput.setAttribute('aria-invalid', String(Boolean(message)));
  if (message) todoFeedback.textContent = message;
  else if (todoFeedback.textContent.includes('마감일')) todoFeedback.textContent = '';
}

function resetForm() {
  editingId = null;
  form.reset();
  submitButton.textContent = '추가';
  cancelEditButton.hidden = true;
  todoFeedback.textContent = '';
  input.setAttribute('aria-invalid', 'false');
  dueDateInput.setCustomValidity('');
  dueDateInput.setAttribute('aria-invalid', 'false');
  input.focus();
}

form.addEventListener('submit', event => {
  event.preventDefault();
  const text = input.value.trim();
  if (!text) {
    todoFeedback.textContent = '할 일을 입력해 주세요.';
    input.setAttribute('aria-invalid', 'true');
    input.focus();
    return;
  }
  if (editingId) {
    const todo = todos.find(item => item.id === editingId);
    if (todo) {
      todo.text = text;
      todo.priority = priorityInput.value;
      todo.dueDate = dueDateInput.value;
    }
  } else {
    todos.push({
      id: String(Date.now()),
      text,
      done: false,
      priority: priorityInput.value,
      dueDate: dueDateInput.value
    });
  }
  resetForm();
  render();
});

cancelEditButton.addEventListener('click', resetForm);
input.addEventListener('input', () => {
  if (!input.value.trim()) return;
  todoFeedback.textContent = '';
  input.setAttribute('aria-invalid', 'false');
});
input.addEventListener('keydown', event => {
  if (event.key !== 'Enter' || event.isComposing) return;
  event.preventDefault();
  form.requestSubmit();
});
dueDateInput.addEventListener('input', updateDueDate);

list.addEventListener('click', event => {
  const item = event.target.closest('li');
  if (!item) return;
  if (event.target.classList.contains('delete')) {
    todos = todos.filter(todo => todo.id !== item.dataset.id);
    if (editingId === item.dataset.id) resetForm();
  }
  if (event.target.classList.contains('toggle')) {
    const todo = todos.find(todo => todo.id === item.dataset.id);
    todo.done = !todo.done;
  }
  if (event.target.classList.contains('edit')) {
    const todo = todos.find(todo => todo.id === item.dataset.id);
    editingId = todo.id;
    input.value = todo.text;
    priorityInput.value = todo.priority || 'normal';
    dueDateInput.value = todo.dueDate || '';
    updateDueDate();
    submitButton.textContent = '수정 저장';
    cancelEditButton.hidden = false;
    input.focus();
    return;
  }
  render();
});

filters.addEventListener('click', event => {
  if (!event.target.dataset.filter) return;
  currentFilter = event.target.dataset.filter;
  for (const button of filters.querySelectorAll('button[data-filter]')) {
    const isActive = button === event.target;
    button.classList.toggle('active', isActive);
    button.setAttribute('aria-pressed', String(isActive));
  }
  render();
});

async function loadQuote() {
  try {
    const response = await fetch('https://dummyjson.com/quotes/random');
    if (!response.ok) throw new Error();
    const data = await response.json();
    document.querySelector('#quote').textContent = data.quote;
  } catch {
    document.querySelector('#quote').textContent = '오늘 할 일을 하나씩 완료해 보세요.';
  }
}

render();
loadQuote();

