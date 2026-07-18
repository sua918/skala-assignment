export function createGame(best, onBest) {
  let answer = Math.floor(Math.random() * 50) + 1;
  let attempts = 0;
  const form = document.querySelector('#game-form');
  const input = document.querySelector('#game-number');
  const result = document.querySelector('#game-result');
  const count = document.querySelector('#game-attempts');
  const bestBox = document.querySelector('#game-best');
  bestBox.textContent = best || '-';

  function reset() { answer = Math.floor(Math.random() * 50) + 1; attempts = 0; count.textContent = '0'; result.textContent = '새 게임이 준비되었습니다.'; input.value = ''; }
  form.addEventListener('submit', event => {
    event.preventDefault();
    const number = Number(input.value);
    if (!Number.isInteger(number) || number < 1 || number > 50) { result.textContent = '1부터 50 사이의 정수를 입력하세요.'; return; }
    attempts += 1; count.textContent = attempts;
    if (number === answer) {
      result.textContent = `정답입니다! ${attempts}번 만에 찾았습니다.`;
      if (!best || attempts < best) { best = attempts; bestBox.textContent = best; onBest(best); }
    } else result.textContent = number > answer ? `${number}보다 작습니다. DOWN!` : `${number}보다 큽니다. UP!`;
    input.select();
  });
  document.querySelector('#game-reset').addEventListener('click', reset);
}

export function initGrade() {
  document.querySelector('#grade-form').addEventListener('submit', event => {
    event.preventDefault();
    const scores = [...new FormData(event.currentTarget)].map(([name, value]) => [name, Number(value)]);
    const invalid = scores.some(([, value]) => value < 0 || value > 100 || !Number.isFinite(value));
    const result = document.querySelector('#grade-result');
    if (invalid || scores.length !== 3) { result.textContent = '각 과목에 0~100점 사이의 점수를 입력하세요.'; return; }
    const average = scores.reduce((sum, [, value]) => sum + value, 0) / scores.length;
    const weak = scores.reduce((lowest, current) => current[1] < lowest[1] ? current : lowest);
    const grade = average >= 90 ? 'A' : average >= 80 ? 'B' : average >= 70 ? 'C' : average >= 60 ? 'D' : 'F';
    const target = Math.max(0, 80 * scores.length - scores.reduce((sum, [, value]) => sum + value, 0));
    result.textContent = `평균 ${average.toFixed(1)}점 · ${grade}등급 · 보완 과목은 ${weak[0]}입니다.${target ? ` 평균 80점까지 총 ${target}점이 더 필요해요.` : ' 목표 평균 80점을 달성했어요.'}`;
  });
}
