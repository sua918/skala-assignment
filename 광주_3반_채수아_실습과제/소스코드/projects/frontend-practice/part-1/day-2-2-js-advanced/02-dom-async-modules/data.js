export const subjects = ['HTML', 'CSS', 'JavaScript'];

export function getSubjects() {
  return new Promise(resolve => setTimeout(() => resolve(subjects), 1000));
}

