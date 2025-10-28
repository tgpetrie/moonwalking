// BHABIT logo loader disabled in dev: no-op to avoid automatic logo injection.
// If you need the logo injection behavior, restore the original loader implementation
// from project history or static-demo/bhabit-logo-loader.js.
(function(){
  // intentionally do nothing
  try {
    if (typeof window !== 'undefined' && window.console && window.console.debug) {
      window.console.debug('[bhabit-logo-loader] disabled');
    }
  } catch (e) {
    // ignore
  }
})();
