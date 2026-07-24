// Ask Bhabit — feature orchestrator.
//
// Validates the core loop: immediate sample value → manual entry → optional
// thesis → structured position-aware answer → feedback. State is a small
// machine; the analysis itself is delegated to a resolver prop (fixtures by
// default) so the backend can be swapped in without touching the UI.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import PropTypes from "prop-types";

import "./styles/ask-bhabit.css";
import { ANALYSIS_STATE } from "./askBhabitContract.js";
import { buildAnalysisView } from "./askBhabitAdapter.js";
import { useBetaAllowance } from "./useBetaAllowance.js";
import { defaultResolveAnalysis } from "./defaultResolver.js";
import { ANALYTICS_EVENTS, emit } from "./analytics.js";

import BetaAllowanceMeter from "./components/BetaAllowanceMeter.jsx";
import SamplePositions from "./components/SamplePositions.jsx";
import GuidedQuestions from "./components/GuidedQuestions.jsx";
import PositionForm from "./components/PositionForm.jsx";
import ThesisForm from "./components/ThesisForm.jsx";
import AnswerView from "./components/AnswerView.jsx";
import FeedbackControls from "./components/FeedbackControls.jsx";

export default function AskBhabitExperience({ resolveAnalysis = defaultResolveAnalysis, betaLimit }) {
  const allowance = useBetaAllowance(betaLimit);
  const [position, setPosition] = useState(null); // active position (sample or manual)
  const [isSample, setIsSample] = useState(false);
  const [showManualForm, setShowManualForm] = useState(false);
  const [showThesisForm, setShowThesisForm] = useState(false);
  const [activeQuestionId, setActiveQuestionId] = useState(null);
  const [analysis, setAnalysis] = useState({ state: ANALYSIS_STATE.IDLE });
  const askedAssets = useRef(new Set());
  const askedOnce = useRef(false);

  // Return-session instrumentation (fires once per mount).
  useEffect(() => {
    emit(ANALYTICS_EVENTS.RETURN_SESSION, { remaining: allowance.remaining });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const selectSample = useCallback((sample) => {
    setPosition(sample);
    setIsSample(true);
    setShowManualForm(false);
    setShowThesisForm(false);
    setActiveQuestionId(null);
    setAnalysis({ state: ANALYSIS_STATE.IDLE });
    emit(ANALYTICS_EVENTS.SAMPLE_PORTFOLIO_OPENED, { asset: sample.asset });
  }, []);

  const saveManualPosition = useCallback((normalized, { costBasisEntered } = {}) => {
    setPosition({ ...normalized, isSample: false });
    setIsSample(false);
    setShowManualForm(false);
    setShowThesisForm(true);
    setActiveQuestionId(null);
    setAnalysis({ state: ANALYSIS_STATE.IDLE });
    emit(ANALYTICS_EVENTS.POSITION_ADDED_MANUALLY, { asset: normalized.asset });
    if (costBasisEntered) emit(ANALYTICS_EVENTS.COST_BASIS_ENTERED, { asset: normalized.asset });
  }, []);

  const saveThesis = useCallback(
    (thesis) => {
      setPosition((p) => (p ? { ...p, thesis } : p));
      setShowThesisForm(false);
      emit(ANALYTICS_EVENTS.THESIS_ADDED, { asset: position?.asset, horizon: thesis.horizon, tags: thesis.tags });
    },
    [position]
  );

  const runAnalysis = useCallback(
    async (question) => {
      if (!position) return;

      // Only real analyses consume the founder-funded allowance; samples are free.
      if (!isSample) {
        if (allowance.exhausted) {
          setAnalysis({ state: ANALYSIS_STATE.TRIAL_EXHAUSTED });
          return;
        }
        allowance.consume();
      }

      // Repeat vs different-asset instrumentation.
      const asset = String(position.asset || "").toUpperCase();
      emit(askedAssets.current.has(asset) ? ANALYTICS_EVENTS.REPEAT_ASSET_QUERY : ANALYTICS_EVENTS.DIFFERENT_ASSET_QUERY, { asset });
      askedAssets.current.add(asset);
      if (!askedOnce.current) {
        askedOnce.current = true;
        emit(ANALYTICS_EVENTS.FIRST_QUESTION_ASKED, { asset, question: question.id });
      }

      setActiveQuestionId(question.id);
      setAnalysis({ state: ANALYSIS_STATE.LOADING });

      try {
        const raw = await resolveAnalysis({ position, question, isSample });
        const result = buildAnalysisView(raw);
        setAnalysis(result);
        if (result.state === ANALYSIS_STATE.READY) {
          if (isSample) emit(ANALYTICS_EVENTS.SAMPLE_ANALYSIS_VIEWED, { asset });
          emit(ANALYTICS_EVENTS.ANSWER_COMPLETED, { asset, question: question.id, confidence: result.view.confidence.level });
          if (result.view.missing.some((m) => m.status === "unsupported")) {
            emit(ANALYTICS_EVENTS.UNSUPPORTED_DATA_WARNING_SHOWN, { asset });
          }
        } else {
          emit(ANALYTICS_EVENTS.ANSWER_FAILED, { asset, state: result.state });
        }
      } catch (err) {
        setAnalysis({ state: ANALYSIS_STATE.PROVIDER_ERROR, message: err?.message || "Request failed." });
        emit(ANALYTICS_EVENTS.ANSWER_FAILED, { asset, error: err?.message });
      }
    },
    [position, isSample, allowance, resolveAnalysis]
  );

  const rateAnswer = useCallback(
    ({ kind, note }) => emit(ANALYTICS_EVENTS.ANSWER_RATED, { asset: position?.asset, kind, hasNote: Boolean(note) }),
    [position]
  );

  const isStale =
    analysis.state === ANALYSIS_STATE.READY &&
    (analysis.view.sources.some((s) => s.freshness === "stale") ||
      analysis.view.missing.some((m) => m.status === "stale"));
  const askDisabled = analysis.state === ANALYSIS_STATE.LOADING;
  const showGuided = position && !showThesisForm;

  const headerNote = useMemo(() => {
    if (!position) return "See a sample read, then add your own position.";
    return isSample ? `Sample position · ${position.asset}` : `Your position · ${position.asset}`;
  }, [position, isSample]);

  return (
    <div className="abx" data-testid="ask-bhabit">
      <header className="abx-head">
        <h2 className="abx-title">Ask Bhabit</h2>
        <span className="abx-beta">Beta</span>
      </header>

      <BetaAllowanceMeter {...allowance} />

      {!position ? (
        <>
          <SamplePositions selectedId={null} onSelect={selectSample} />
          <div className="abx-actions" style={{ marginBottom: 12 }}>
            <button type="button" className="abx-btn abx-btn-ghost" onClick={() => setShowManualForm((v) => !v)}>
              {showManualForm ? "Hide manual entry" : "Add a real position"}
            </button>
          </div>
          {showManualForm ? <PositionForm onSubmit={saveManualPosition} onCancel={() => setShowManualForm(false)} /> : null}
        </>
      ) : (
        <>
          <p className="abx-eyebrow">{headerNote}</p>

          {showThesisForm ? (
            <ThesisForm onSave={saveThesis} onSkip={() => setShowThesisForm(false)} />
          ) : null}

          {showGuided ? (
            <GuidedQuestions disabled={askDisabled} activeId={activeQuestionId} onAsk={runAnalysis} />
          ) : null}

          {isStale ? (
            <div className="abx-stale-banner" role="alert">⚠ Some data is stale — read the Missing &amp; uncertain section.</div>
          ) : null}

          <AnalysisPane analysis={analysis} onCitationOpen={(s) => emit(ANALYTICS_EVENTS.CITATION_OPENED, { provider: s.provider })} onRetry={() => activeQuestionId && runAnalysis({ id: activeQuestionId })} onRate={rateAnswer} />

          <div className="abx-actions" style={{ marginTop: 8 }}>
            <button
              type="button"
              className="abx-btn abx-btn-ghost"
              onClick={() => {
                setPosition(null);
                setIsSample(false);
                setAnalysis({ state: ANALYSIS_STATE.IDLE });
                setActiveQuestionId(null);
              }}
            >
              Back to positions
            </button>
          </div>
        </>
      )}
    </div>
  );
}

function AnalysisPane({ analysis, onCitationOpen, onRetry, onRate }) {
  switch (analysis.state) {
    case ANALYSIS_STATE.LOADING:
      return (
        <div className="abx-loading" role="status" aria-live="polite">
          <div className="abx-spinner" aria-hidden="true" />
          <p className="abx-state-detail">Gathering evidence…</p>
        </div>
      );
    case ANALYSIS_STATE.PROVIDER_ERROR:
      return (
        <StateCard title="Data provider unavailable" detail={analysis.message} tone="danger" onRetry={onRetry} />
      );
    case ANALYSIS_STATE.MODEL_FAILURE:
      return <StateCard title="Analysis failed" detail={analysis.message} tone="danger" onRetry={onRetry} />;
    case ANALYSIS_STATE.TRIAL_EXHAUSTED:
      return (
        <StateCard
          title="Beta allowance used"
          detail="Your beta analysis allowance has been used. More access is coming soon."
          tone="warning"
        />
      );
    case ANALYSIS_STATE.READY:
      return (
        <>
          <AnswerView view={analysis.view} onCitationOpen={onCitationOpen} />
          <FeedbackControls onRate={onRate} />
        </>
      );
    default:
      return null;
  }
}

function StateCard({ title, detail, tone, onRetry }) {
  return (
    <div className="abx-state" role="alert">
      <p className={`abx-state-title abx-tone-${tone || "muted"}`}>{title}</p>
      <p className="abx-state-detail">{detail}</p>
      {onRetry ? (
        <div className="abx-actions" style={{ justifyContent: "center", marginTop: 12 }}>
          <button type="button" className="abx-btn abx-btn-ghost" onClick={onRetry}>Retry</button>
        </div>
      ) : null}
    </div>
  );
}

AnalysisPane.propTypes = {
  analysis: PropTypes.object.isRequired,
  onCitationOpen: PropTypes.func,
  onRetry: PropTypes.func,
  onRate: PropTypes.func,
};
StateCard.propTypes = {
  title: PropTypes.string,
  detail: PropTypes.string,
  tone: PropTypes.string,
  onRetry: PropTypes.func,
};

AskBhabitExperience.propTypes = {
  resolveAnalysis: PropTypes.func,
  betaLimit: PropTypes.number,
};
