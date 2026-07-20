const themeButton = document.querySelector('#themeButton');
const savedTheme = localStorage.getItem('simple-shop-theme');
const searchInput = document.querySelector('#productSearch');
const categoryFilters = document.querySelector('.category-filters');
const productCount = document.querySelector('#productCount');
const emptyProducts = document.querySelector('#emptyProducts');
const productCards = [...document.querySelectorAll('.product-card')];
const favoriteKey = 'simple-shop-favorites';
let currentCategory = 'all';
let favorites = loadFavorites();

function loadFavorites() {
  try {
    const saved = JSON.parse(localStorage.getItem(favoriteKey));
    return Array.isArray(saved) ? new Set(saved) : new Set();
  } catch {
    return new Set();
  }
}

function saveFavorites() {
  localStorage.setItem(favoriteKey, JSON.stringify([...favorites]));
}

function addFavoriteButtons() {
  for (const card of productCards) {
    const button = document.createElement('button');
    button.className = 'favorite-button';
    button.type = 'button';
    button.dataset.favoriteId = card.dataset.id;
    button.setAttribute('aria-label', `${card.querySelector('h3').textContent} 관심 상품`);
    card.querySelector('.product-visual').append(button);
    updateFavoriteButton(button);
  }
}

function updateFavoriteButton(button) {
  const isFavorite = favorites.has(button.dataset.favoriteId);
  button.classList.toggle('selected', isFavorite);
  button.setAttribute('aria-pressed', String(isFavorite));
  button.textContent = isFavorite ? '♥' : '♡';
}

function renderProducts() {
  const keyword = searchInput.value.trim().toLowerCase();
  let visibleCount = 0;

  for (const card of productCards) {
    const categoryMatch = currentCategory === 'all'
      || card.dataset.category === currentCategory
      || (currentCategory === 'favorite' && favorites.has(card.dataset.id));
    const keywordMatch = card.dataset.search.toLowerCase().includes(keyword);
    const isVisible = categoryMatch && keywordMatch;
    card.hidden = !isVisible;
    if (isVisible) visibleCount += 1;
  }

  productCount.textContent = `총 ${visibleCount}개의 상품`;
  emptyProducts.hidden = visibleCount !== 0;
}

function updateThemeButton(isDark) {
  themeButton.textContent = isDark ? '☀️ 라이트' : '🌙 다크';
  themeButton.setAttribute('aria-pressed', String(isDark));
}

if (savedTheme === 'dark') {
  document.body.classList.add('dark');
}

updateThemeButton(document.body.classList.contains('dark'));

themeButton.addEventListener('click', () => {
  const isDark = document.body.classList.toggle('dark');
  localStorage.setItem('simple-shop-theme', isDark ? 'dark' : 'light');
  updateThemeButton(isDark);
});

searchInput.addEventListener('input', renderProducts);

categoryFilters.addEventListener('click', event => {
  const button = event.target.closest('button[data-category]');
  if (!button) return;
  currentCategory = button.dataset.category;
  for (const filterButton of categoryFilters.querySelectorAll('button[data-category]')) {
    const isActive = filterButton === button;
    filterButton.classList.toggle('active', isActive);
    filterButton.setAttribute('aria-pressed', String(isActive));
  }
  renderProducts();
});

document.querySelector('.product-grid').addEventListener('click', event => {
  const button = event.target.closest('.favorite-button');
  if (!button) return;
  const id = button.dataset.favoriteId;
  if (favorites.has(id)) favorites.delete(id);
  else favorites.add(id);
  saveFavorites();
  updateFavoriteButton(button);
  if (currentCategory === 'favorite') renderProducts();
});

addFavoriteButtons();
renderProducts();
