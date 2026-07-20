const question = {
  text: '클릭 이벤트를 연결할 때 사용하는 메서드는?',
  choices: ['querySelector()', 'addEventListener()', 'createElement()'],
  answer: 1
};

const quiz = document.querySelector('#quiz');
const heading = document.createElement('h2');
heading.textContent = question.text;
quiz.append(heading);

question.choices.forEach((choice, index) => {
  const button = document.createElement('button');
  button.textContent = choice;
  button.addEventListener('click', () => {
    const correct = index === question.answer;
    const result = document.querySelector('#result');
    result.textContent = correct ? '정답입니다.' : '오답입니다.';
    result.className = correct ? 'correct' : 'wrong';
  });
  quiz.append(button);
});

