// Simple non-module loader that replaces <img data-bhabit-logo> or elements with data-bhabit-logo
(function(){
  try {
    const SRC = '/bhabit-logo-main.svg';
    const query = '[data-bhabit-logo]';
    const nodes = Array.from(document.querySelectorAll(query));
    if (nodes.length === 0) return;
    nodes.forEach((el) => {
      if (el.tagName === 'IMG') {
        el.src = SRC;
        el.setAttribute('alt', 'BHABIT');
      } else {
        // inject an image node for non-img elements
        const img = document.createElement('img');
        img.src = SRC;
        img.alt = 'BHABIT';
        img.width = el.getAttribute('data-bhabit-width') || 160;
        img.height = el.getAttribute('data-bhabit-height') || 48;
        el.appendChild(img);
      }
    });
  } catch (e) {
    // graceful degrade
    try { console.error('bhabit-logo-loader failed', e); } catch (_) {}
  }
})();
