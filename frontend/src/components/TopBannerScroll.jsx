// Shim: TypeScript entry that re-exports the JSX implementation.
// This avoids duplicate components (one in .tsx, one in .jsx) and keeps a single source of truth.

import TopBannerScroll from './TopBannerScroll.jsx';
export default TopBannerScroll;