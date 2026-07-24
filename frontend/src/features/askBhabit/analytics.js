// Lightweight instrumentation wrapper — no analytics dependency.
//
// The brief lists a fixed set of events. This wrapper gives us a single choke
// point: today it buffers events and mirrors them to a debug sink; wiring a real
// backend later means editing only `emit`. Components call the named helpers so
// event names can't drift into typos.

export const ANALYTICS_EVENTS = Object.freeze({
  SAMPLE_PORTFOLIO_OPENED: "sample_portfolio_opened",
  SAMPLE_ANALYSIS_VIEWED: "sample_analysis_viewed",
  POSITION_ADDED_MANUALLY: "position_added_manually",
  COST_BASIS_ENTERED: "cost_basis_entered",
  THESIS_ADDED: "thesis_added",
  FIRST_QUESTION_ASKED: "first_question_asked",
  ANSWER_COMPLETED: "answer_completed",
  ANSWER_FAILED: "answer_failed",
  ANSWER_RATED: "answer_rated",
  CITATION_OPENED: "citation_opened",
  UNSUPPORTED_DATA_WARNING_SHOWN: "unsupported_data_warning_shown",
  REPEAT_ASSET_QUERY: "repeat_asset_query",
  DIFFERENT_ASSET_QUERY: "different_asset_query",
  RETURN_SESSION: "return_session",
  SEVEN_DAY_RETURN: "seven_day_return",
});

const buffer = [];
const MAX_BUFFER = 200;

// Swappable sink. Tests can override via setAnalyticsSink to assert emissions
// without reaching into module internals.
let sink = (event) => {
  if (typeof window !== "undefined" && window.__ASK_BHABIT_DEBUG__) {
    // eslint-disable-next-line no-console
    console.debug("[ask-bhabit]", event.name, event.props);
  }
};

export function setAnalyticsSink(fn) {
  sink = typeof fn === "function" ? fn : sink;
}

export function emit(name, props = {}) {
  const event = { name, props, at: new Date().toISOString() };
  buffer.push(event);
  if (buffer.length > MAX_BUFFER) buffer.shift();
  try {
    sink(event);
  } catch {
    /* instrumentation must never break the app */
  }
  return event;
}

export const getBufferedEvents = () => buffer.slice();
