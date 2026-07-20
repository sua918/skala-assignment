const title = document.querySelector('#title');
const input = document.querySelector('#itemInput');
const list = document.querySelector('#itemList');

document.querySelector('#changeButton').addEventListener('click', () => {
  title.textContent = '제목이 변경되었습니다.';
  title.classList.toggle('done');
});

document.querySelector('#addButton').addEventListener('click', () => {
  const text = input.value.trim();
  if (!text) return;
  const item = document.createElement('li');
  item.textContent = `${text} `;
  const removeButton = document.createElement('button');
  removeButton.textContent = '삭제';
  removeButton.addEventListener('click', () => item.remove());
  item.append(removeButton);
  list.append(item);
  input.value = '';
});

