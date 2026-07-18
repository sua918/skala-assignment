const KEY = 'skalaDashboard.v1';

const defaults = {
  profile: { name: '수아', interest: 'frontend', intro: '작은 목표부터 차근차근 시작해 보세요.' },
  goals: [
    { id: 'security', text: '정보보안기사 실기 합격하기', done: false },
    { id: 'toeic', text: '토익 800점대 만들기', done: false },
    { id: 'resume', text: '기업에 이력서 넣어보기', done: false },
    { id: 'skct', text: 'SKCT 시험 준비하기', done: false }
  ],
  classChecks: {}, favorites: [], bagChecks: {}, dailyRecords: {}, routine: null, gameBest: null, weatherCache: null, configured: false
};

function clone(value) { return JSON.parse(JSON.stringify(value)); }

export function loadState() {
  try {
    const saved = JSON.parse(localStorage.getItem(KEY));
    return saved ? { ...clone(defaults), ...saved, profile: { ...defaults.profile, ...saved.profile } } : clone(defaults);
  } catch { return clone(defaults); }
}

export function saveState(state) { localStorage.setItem(KEY, JSON.stringify(state)); }
export function resetState() { localStorage.removeItem(KEY); }

