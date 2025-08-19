// Compatibility shim: some code imports `GainersTable1m.jsx` (lowercase 'm')
// but the canonical file in this repo is `GainersTable1Min.jsx`.
// Re-export the default to avoid duplicate implementations and fix Vite import errors.
import GainersTable1Min from './GainersTable1Min.jsx';

export default GainersTable1Min;
