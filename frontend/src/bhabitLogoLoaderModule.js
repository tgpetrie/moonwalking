// Module-based BHABIT logo loader (for bundlers)
// Mirrors the behavior of the public non-module loader but is safe to import from src.
export default (function(){
  try {
    const SRC = '/bhabit-logo-main.svg';
    const query = '[data-bhabit-logo]';
    const nodes = Array.from(document.querySelectorAll(query));
    if (nodes.length === 0) return;
    nodes.forEach((el, idx) => {
      if (el.tagName === 'IMG') {
        el.src = SRC;
        el.setAttribute('alt', 'BHABIT');
      } else {
        const img = document.createElement('img');
        img.src = SRC;
        img.alt = 'BHABIT';
        img.width = el.getAttribute('data-bhabit-width') || 160;
        img.height = el.getAttribute('data-bhabit-height') || 48;
        el.appendChild(img);
      }
    });
  } catch (err) {
    console.error('bhabitLogoLoaderModule error', err);
  }
})();
