const form = document.querySelector('#signupForm');
const userId = document.querySelector('#userId');
const userIdHint = document.querySelector('#userIdHint');
const password = document.querySelector('#password');
const passwordConfirm = document.querySelector('#passwordConfirm');
const passwordStrength = document.querySelector('#passwordStrength');
const passwordConfirmHint = document.querySelector('#passwordConfirmHint');
const strengthBar = document.querySelector('#strengthBar');
const togglePassword = document.querySelector('#togglePassword');
const birthDate = document.querySelector('#birthDate');
const birthDateHint = document.querySelector('#birthDateHint');
const introduction = document.querySelector('#introduction');
const introCount = document.querySelector('#introCount');
const draftStatus = document.querySelector('#draftStatus');
const draftKey = 'registration-profile-draft';

function updateUserIdHint() {
  if (!userId.value) {
    setHint(userIdHint, '영문과 숫자를 조합해 4~12자로 입력하세요.', '');
    return;
  }
  const isValid = userId.validity.valid;
  setHint(userIdHint, isValid ? '영문과 숫자를 포함한 사용 가능한 형식입니다.' : '영문과 숫자를 모두 포함해 4~12자로 입력하세요.', isValid ? 'valid' : 'invalid');
}

function updatePasswordStatus() {
  const value = password.value;
  let score = 0;
  if (value.length >= 8) score += 1;
  if (/[A-Za-z]/.test(value) && /\d/.test(value)) score += 1;
  if (/[^A-Za-z0-9]/.test(value)) score += 1;
  const labels = ['8자 이상 입력하세요.', '보통 · 문자와 숫자를 섞어 보세요.', '안전 · 기본 조건을 충족했습니다.', '강함 · 특수문자까지 포함했습니다.'];
  const widths = ['0%', '34%', '67%', '100%'];
  const colors = ['#b42318', '#b54708', '#167443', '#0f6b47'];
  passwordStrength.textContent = labels[score];
  passwordStrength.className = `field-hint ${score >= 2 ? 'valid' : value ? 'invalid' : ''}`;
  strengthBar.style.width = widths[score];
  strengthBar.style.background = colors[score];
  updatePasswordConfirm();
}

function updatePasswordConfirm() {
  const matches = passwordConfirm.value && password.value === passwordConfirm.value;
  passwordConfirm.setCustomValidity(passwordConfirm.value && !matches ? '비밀번호가 일치하지 않습니다.' : '');
  if (!passwordConfirm.value) {
    setHint(passwordConfirmHint, '같은 비밀번호를 한 번 더 입력하세요.', '');
  } else {
    setHint(passwordConfirmHint, matches ? '비밀번호가 일치합니다.' : '비밀번호가 일치하지 않습니다.', matches ? 'valid' : 'invalid');
  }
}

function setHint(element, message, state) {
  element.textContent = message;
  element.className = `field-hint ${state}`.trim();
}

function updateIntroCount() {
  introCount.textContent = `${introduction.value.length} / 200자`;
}

function updateBirthDate() {
  if (!birthDate.value) {
    birthDate.setCustomValidity('');
    setHint(birthDateHint, '달력에서 생년월일을 선택하세요.', '');
    return;
  }

  let message = '';
  if (birthDate.value < birthDate.min) message = '1900년 이후 날짜를 선택하세요.';
  else if (birthDate.value > birthDate.max) message = '오늘 이후의 날짜는 선택할 수 없습니다.';

  birthDate.setCustomValidity(message);
  setHint(birthDateHint, message || '생년월일이 선택되었습니다.', message ? 'invalid' : 'valid');
}

function getLocalDateValue(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function saveDraft() {
  const draft = {};
  for (const field of form.elements) {
    if (!field.name || ['password', 'terms'].includes(field.name)) continue;
    if (field.type === 'checkbox') {
      if (!draft[field.name]) draft[field.name] = [];
      if (field.checked) draft[field.name].push(field.value);
    } else if (field.type === 'radio') {
      if (field.checked) draft[field.name] = field.value;
    } else {
      draft[field.name] = field.value;
    }
  }
  localStorage.setItem(draftKey, JSON.stringify(draft));
  draftStatus.textContent = '민감정보를 제외한 작성 내용이 임시 저장되었습니다.';
}

function restoreDraft() {
  try {
    const draft = JSON.parse(localStorage.getItem(draftKey));
    if (!draft) return;
    for (const field of form.elements) {
      if (!field.name || draft[field.name] === undefined) continue;
      if (field.type === 'checkbox') field.checked = draft[field.name].includes(field.value);
      else if (field.type === 'radio') field.checked = draft[field.name] === field.value;
      else field.value = draft[field.name];
    }
    draftStatus.textContent = '이전에 작성하던 내용을 복원했습니다.';
  } catch {
    localStorage.removeItem(draftKey);
  }
}

userId.addEventListener('input', updateUserIdHint);
password.addEventListener('input', updatePasswordStatus);
passwordConfirm.addEventListener('input', updatePasswordConfirm);
birthDate.addEventListener('input', updateBirthDate);
introduction.addEventListener('input', updateIntroCount);
form.addEventListener('input', saveDraft);
form.addEventListener('change', saveDraft);
form.addEventListener('reset', () => {
  localStorage.removeItem(draftKey);
  setTimeout(() => {
    updateUserIdHint();
    updatePasswordStatus();
    updateBirthDate();
    updateIntroCount();
    draftStatus.textContent = '작성 내용이 초기화되었습니다.';
  });
});
form.addEventListener('submit', () => localStorage.removeItem(draftKey));

togglePassword.addEventListener('click', () => {
  const shouldShow = password.type === 'password';
  password.type = shouldShow ? 'text' : 'password';
  passwordConfirm.type = shouldShow ? 'text' : 'password';
  togglePassword.textContent = shouldShow ? '숨기기' : '보기';
  togglePassword.setAttribute('aria-pressed', String(shouldShow));
});

restoreDraft();
birthDate.max = getLocalDateValue(new Date());
updateUserIdHint();
updatePasswordStatus();
updatePasswordConfirm();
updateBirthDate();
updateIntroCount();
