const KEY = 'frontend-practice-todos-v2';
const LEGACY_KEY = 'frontend-practice-todos';
const DEFAULT_TODOS = [
  {
    id: 'starter-html',
    text: 'HTML 시맨틱 태그 복습',
    done: false,
    priority: 'normal',
    dueDate: ''
  },
  {
    id: 'starter-javascript',
    text: 'JavaScript DOM 이벤트 실습',
    done: false,
    priority: 'high',
    dueDate: ''
  }
];

export function loadTodos() {
  try {
    const saved = localStorage.getItem(KEY);
    if (saved !== null) {
      const todos = JSON.parse(saved);
      return Array.isArray(todos) ? todos : [];
    }

    const legacyTodos = JSON.parse(localStorage.getItem(LEGACY_KEY));
    if (Array.isArray(legacyTodos) && legacyTodos.length) return legacyTodos;
    return DEFAULT_TODOS.map(todo => ({ ...todo }));
  } catch {
    return DEFAULT_TODOS.map(todo => ({ ...todo }));
  }
}

export function saveTodos(todos) {
  localStorage.setItem(KEY, JSON.stringify(todos));
}

