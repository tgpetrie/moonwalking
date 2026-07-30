// Maps a semantic tone to the .abx tone class. One place so a renamed tone can't
// silently fall back to invisible text.
const TONES = new Set(["positive", "info", "warning", "danger", "muted", "neutral"]);
export const toneClass = (tone) => `abx-tone-${TONES.has(tone) ? tone : "muted"}`;
