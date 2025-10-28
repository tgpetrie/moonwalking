// Public BHABIT logo loader disabled: no-op to avoid automatic DOM mutation.
(function(){
	try {
		if (typeof window !== 'undefined' && window.console && window.console.debug) {
			window.console.debug('[public/bhabit-logo-loader] disabled');
		}
		// Provide a no-op global named function for compatibility with legacy pages
		window.BHABITLogoRefresh = function(){ if (window && window.console && window.console.debug) window.console.debug('[public/bhabit-logo-loader] BHABITLogoRefresh noop'); };
	} catch (e) {
		// ignore errors
	}
})();
