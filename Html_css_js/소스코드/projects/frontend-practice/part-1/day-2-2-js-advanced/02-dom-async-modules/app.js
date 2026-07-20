import { getSubjects } from './data.js';

document.querySelector('#loadButton').addEventListener('click', async () => {
  const status = document.querySelector('#status');
  const list = document.querySelector('#dataList');
  status.textContent = '불러오는 중...';
  const subjects = await getSubjects();
  list.replaceChildren();
  for (const subject of subjects) {
    const item = document.createElement('li');
    item.textContent = subject;
    list.append(item);
  }
  status.textContent = '완료';
});

