const student = { name: '홍길동', scores: [80, 70, 90] };

function calculateAverage(scores) {
  let total = 0;
  for (const score of scores) total += score;
  return total / scores.length;
}

document.querySelector('#runButton').addEventListener('click', () => {
  const average = calculateAverage(student.scores);
  const pass = average >= 60 ? '합격' : '불합격';
  document.querySelector('#result').textContent = `${student.name}\n점수: ${student.scores.join(', ')}\n평균: ${average}\n결과: ${pass}`;
  console.log(student);
});

