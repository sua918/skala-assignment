const labels = {
  name: '이름', userId: '아이디', password: '비밀번호', email: '이메일', phone: '전화번호',
  birthDate: '생년월일', gender: '성별', interest: '관심 분야',
  region: '지역', introduction: '자기소개', terms: '약관 동의'
};
const params = new URLSearchParams(location.search);
const body = document.querySelector('#resultBody');

for (const [name, label] of Object.entries(labels)) {
  const values = params.getAll(name);
  const row = document.createElement('tr');
  const heading = document.createElement('th');
  const value = document.createElement('td');
  heading.textContent = label;
  const displayValues = values.filter(Boolean);
  value.textContent = name === 'password'
    ? '보안을 위해 전송하지 않음'
    : (displayValues.length ? displayValues.join(', ') : '-');
  row.append(heading, value);
  body.append(row);
}

const profileCard = document.querySelector('#profileCard');
const name = params.get('name') || '새로운 사용자';
const interests = params.getAll('interest').filter(Boolean);
const profileInitial = document.createElement('span');
profileInitial.className = 'profile-initial';
profileInitial.textContent = name.trim().charAt(0) || '?';

const profileCopy = document.createElement('div');
const profileName = document.createElement('h2');
profileName.textContent = name;
const profileMeta = document.createElement('p');
profileMeta.textContent = [params.get('region'), params.get('email')].filter(Boolean).join(' · ') || '기본 프로필';
const profileTags = document.createElement('div');
profileTags.className = 'profile-tags';

for (const interest of interests) {
  const tag = document.createElement('span');
  tag.textContent = interest;
  profileTags.append(tag);
}

if (!interests.length) {
  const tag = document.createElement('span');
  tag.textContent = '관심 분야 미선택';
  profileTags.append(tag);
}

profileCopy.append(profileName, profileMeta, profileTags);
profileCard.append(profileInitial, profileCopy);
