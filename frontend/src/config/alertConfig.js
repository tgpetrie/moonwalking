// Unified alert configuration matching backend moonwalking_alert_system.py
// This ensures consistent icons, labels, and colors across all components

/**
 * Alert Type Configuration
 * Matches backend AlertType enum from moonwalking_alert_system.py
 */
export const ALERT_CONFIG = {
  MOONSHOT: {
    icon: "🚀",
    label: "MOONSHOT",
    displayName: "🚀 MOONSHOT",
    color: "#10b981", // green - massive pump
  },
  CRATER: {
    icon: "📉",
    label: "CRATER",
    displayName: "📉 CRATER",
    color: "#dc2626", // dark red - major dump
  },
  SENTIMENT_SPIKE: {
    icon: "🌊",
    label: "SENTIMENT",
    displayName: "🌊 SENTIMENT",
    color: "#3b82f6", // blue - social sentiment explosion
  },
  WHALE_MOVE: {
    icon: "🐋",
    label: "WHALE",
    displayName: "🐋 WHALE",
    color: "#06b6d4", // cyan - large volume anomaly
  },
  DIVERGENCE: {
    icon: "⚖️",
    label: "DIVERGENCE",
    displayName: "⚖️ DIVERGENCE",
    color: "#a855f7", // purple - price vs sentiment mismatch
  },
  BREAKOUT: {
    icon: "📈",
    label: "BREAKOUT",
    displayName: "📈 BREAKOUT",
    color: "#f59e0b", // amber - technical breakout
  },
  FOMO_ALERT: {
    icon: "🔥",
    label: "FOMO",
    displayName: "🔥 FOMO",
    color: "#ef4444", // red - FOMO/Fear spike
  },
  STEALTH_MOVE: {
    icon: "👤",
    label: "STEALTH",
    displayName: "👤 STEALTH",
    color: "#6366f1", // indigo - quiet accumulation
  },
  NEWS_CATALYST: {
    icon: "📰",
    label: "NEWS",
    displayName: "📰 NEWS",
    color: "#8b5cf6", // violet - news-driven movement
  },
  ARBITRAGE: {
    icon: "💰",
    label: "ARBITRAGE",
    displayName: "💰 ARBITRAGE",
    color: "#14b8a6", // teal - cross-exchange opportunity
  },
  INFO: {
    icon: "ℹ️",
    label: "INFO",
    displayName: "ℹ️ INFO",
    color: "#6b7280", // gray - general info
  },
};

/**
 * Severity Color Configuration
 * Matches backend AlertSeverity enum from moonwalking_alert_system.py
 */
export const SEVERITY_CONFIG = {
  critical: {
    icon: "🔴",
    label: "CRITICAL",
    color: "#dc2626", // red
    tone: "tone-red",
  },
  high: {
    icon: "🟠",
    label: "HIGH",
    color: "#ef4444", // orange-red
    tone: "tone-orange",
  },
  medium: {
    icon: "🟡",
    label: "MEDIUM",
    color: "#f59e0b", // amber/gold
    tone: "tone-gold",
  },
  low: {
    icon: "🟢",
    label: "LOW",
    color: "#3b82f6", // blue (changed from green for better visibility)
    tone: "tone-cyan",
  },
  info: {
    icon: "🔵",
    label: "INFO",
    color: "#6b7280", // gray
    tone: "tone-mint",
  },
};

/**
 * Get alert configuration by type
 * Handles various type formats from backend
 */
export function getAlertConfig(alertType) {
  if (!alertType) return ALERT_CONFIG.INFO;

  // Normalize alert type string
  const normalized = String(alertType).toUpperCase().replace(/\s+/g, "_");

  // Direct match
  if (ALERT_CONFIG[normalized]) {
    return ALERT_CONFIG[normalized];
  }

  // Try without emoji prefix
  const withoutEmoji = normalized.replace(/^[^\w]+/, "");
  if (ALERT_CONFIG[withoutEmoji]) {
    return ALERT_CONFIG[withoutEmoji];
  }

  // Fallback to INFO
  return ALERT_CONFIG.INFO;
}

/**
 * Get severity configuration
 */
export function getSeverityConfig(severity) {
  if (!severity) return SEVERITY_CONFIG.info;

  const normalized = String(severity).toLowerCase().trim();

  return SEVERITY_CONFIG[normalized] || SEVERITY_CONFIG.info;
}

/**
 * Get display color for an alert (prioritizes alert type over severity)
 */
export function getAlertColor(alert) {
  if (!alert) return SEVERITY_CONFIG.info.color;

  // First try alert type
  const alertType = alert.alert_type || alert.type;
  if (alertType) {
    const config = getAlertConfig(alertType);
    if (config && config.color) return config.color;
  }

  // Fallback to severity
  const severity = alert.severity || alert.severity_lc;
  if (severity) {
    const config = getSeverityConfig(severity);
    if (config && config.color) return config.color;
  }

  return SEVERITY_CONFIG.info.color;
}

/**
 * Legacy tone mappings for AnomalyStream
 */
export const SEV_TONE = {
  critical: "tone-red",
  high: "tone-orange",
  medium: "tone-gold",
  low: "tone-cyan",
  info: "tone-mint",
};

/**
 * Legacy type label mappings (without icons) for backwards compatibility
 */
export const TYPE_LABEL = {
  MOONSHOT: "MOONSHOT",
  CRATER: "CRATER",
  SENTIMENT_SPIKE: "SENTIMENT",
  WHALE_MOVE: "WHALE",
  DIVERGENCE: "DIVERGENCE",
  BREAKOUT: "BREAKOUT",
  FOMO_ALERT: "FOMO",
  STEALTH_MOVE: "STEALTH",
  NEWS_CATALYST: "NEWS",
  ARBITRAGE: "ARBITRAGE",
  INFO: "INFO",
};
