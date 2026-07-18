const gallery = document.querySelector('.gallery');
const dialog = document.querySelector('#placeDialog');
const dialogTitle = document.querySelector('#dialogTitle');
const dialogDescription = document.querySelector('#dialogDescription');
const dialogTip = document.querySelector('#dialogTip');
const savedPlacesContainer = document.querySelector('#savedPlaces');
const storageKey = 'west-road-trip-places';
const placeCards = [...document.querySelectorAll('.gallery figure')];
let savedPlaces = loadSavedPlaces();

function loadSavedPlaces() {
  try {
    const saved = JSON.parse(localStorage.getItem(storageKey));
    return Array.isArray(saved) ? new Set(saved) : new Set();
  } catch {
    return new Set();
  }
}

function savePlaces() {
  localStorage.setItem(storageKey, JSON.stringify([...savedPlaces]));
}

function renderSavedPlaces() {
  savedPlacesContainer.replaceChildren();
  const selectedCards = placeCards.filter(card => savedPlaces.has(card.dataset.id));

  if (!selectedCards.length) {
    const empty = document.createElement('span');
    empty.textContent = '저장한 명소가 없습니다.';
    savedPlacesContainer.append(empty);
  } else {
    for (const card of selectedCards) {
      const chip = document.createElement('span');
      chip.textContent = card.dataset.title;
      savedPlacesContainer.append(chip);
    }
  }

  for (const card of placeCards) {
    const button = card.querySelector('.place-save');
    const isSaved = savedPlaces.has(card.dataset.id);
    button.classList.toggle('saved', isSaved);
    button.setAttribute('aria-pressed', String(isSaved));
    button.textContent = isSaved ? '♥ 일정 저장됨' : '♡ 일정 저장';
  }
}

gallery.addEventListener('click', event => {
  const card = event.target.closest('figure');
  if (!card) return;

  if (event.target.closest('.place-detail')) {
    dialogTitle.textContent = card.dataset.title;
    dialogDescription.textContent = card.dataset.description;
    dialogTip.textContent = card.dataset.tip;
    dialog.showModal();
  }

  if (event.target.closest('.place-save')) {
    if (savedPlaces.has(card.dataset.id)) savedPlaces.delete(card.dataset.id);
    else savedPlaces.add(card.dataset.id);
    savePlaces();
    renderSavedPlaces();
  }
});

renderSavedPlaces();
