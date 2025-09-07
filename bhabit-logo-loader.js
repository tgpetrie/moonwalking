(function(){
  const MAP = {
    plain: {
      dark:      './bhabit-logo-plain-dark.svg',
      light:     './bhabit-logo-plain-light.svg',
      'light-hc':'./bhabit-logo-plain-light.svg'
    },
    spray: {
      dark:      './bhabit-logo-spray-dark.svg',
      light:     './bhabit-logo-spray-light.svg',
      'light-hc':'./bhabit-logo-spray-light.svg'
    }
  };
  function theme(){ return document.documentElement.getAttribute('data-theme') || 'dark'; }
  function globalStyle(){ return document.body.getAttribute('data-logo-style') || 'plain'; }
  function pick(el){
    const t = el.getAttribute('data-logo-variant') || theme();
    const s = el.getAttribute('data-logo-style') || globalStyle();
    return (MAP[s]||MAP.plain)[t] || (MAP[s]||MAP.plain).dark;
  }
  function apply(){
    document.querySelectorAll('[data-bhabit-logo]').forEach(el=>{
      const src = pick(el);
      if (el.tagName==='IMG') el.src = src;
      else if (el.tagName==='OBJECT' || el.tagName==='EMBED') el.data = src;
      else el.setAttribute('src', src);
    });
  }
  document.addEventListener('DOMContentLoaded', apply);
  new MutationObserver(m=>{ if (m.some(x=>x.attributeName==='data-theme')) apply(); })
    .observe(document.documentElement,{attributes:true,attributeFilter:['data-theme']});
  window.BHABITLogoRefresh = apply;
})();
