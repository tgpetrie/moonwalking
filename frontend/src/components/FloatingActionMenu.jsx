import React, { useState } from 'react';
import { FiRefreshCw, FiMessageCircle, FiBarChart2, FiBookOpen } from 'react-icons/fi';
import { LuLightbulb } from 'react-icons/lu';
import PropTypes from 'prop-types';

function MenuItem({ icon: Icon, label, onClick, disabled }) {
  return (
    <button
      className={`flex items-center gap-2 px-3 py-2 rounded-full bg-black/70 border border-purple-900 shadow-lg text-sm text-gray-200 hover:text-white hover:bg-black/60 backdrop-blur-sm transition-all ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
      onClick={() => { if (!disabled) onClick?.(); }}
      aria-label={label}
      title={label}
      disabled={disabled}
    >
      <Icon className="text-purple-300" />
      <span className="font-bold">{label}</span>
    </button>
  );
}

MenuItem.propTypes = {
  icon: PropTypes.elementType.isRequired,
  label: PropTypes.string.isRequired,
  onClick: PropTypes.func,
  disabled: PropTypes.bool,
};

/**
 * FloatingActionMenu
 * - Compact FAB that expands into a radial/stack menu on click.
 * - Replaces the intrusive bottom-right button stack.
 */
export default function FloatingActionMenu({
  onRefresh,
  onToggleCodex,
  onToggleInsights,
  onToggleSentiment,
  onToggleLearn,
  disabled = {},
}) {
  const [open, setOpen] = useState(false);

  return (
    <div className="fixed bottom-6 right-6 z-50">
      <div className={`flex flex-col items-end gap-3 transition-all ${open ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2 pointer-events-none'}`}>
        <MenuItem icon={FiRefreshCw} label="Refresh" onClick={() => { onRefresh?.(); setOpen(false); }} disabled={disabled.refresh} />
        <MenuItem icon={FiMessageCircle} label="Ask BHABIT" onClick={() => { onToggleCodex?.(); setOpen(false); }} disabled={disabled.codex} />
        <MenuItem icon={FiBarChart2} label="Insights" onClick={() => { onToggleInsights?.(); setOpen(false); }} disabled={disabled.insights} />
        <MenuItem icon={FiBookOpen} label="Learn" onClick={() => { onToggleLearn?.(); setOpen(false); }} disabled={disabled.learn} />
      </div>
      <button
        onClick={() => setOpen(o => !o)}
        className="w-14 h-14 rounded-full flex items-center justify-center bg-gradient-to-br from-purple-600 to-purple-900 text-white shadow-2xl hover:scale-105 transition-transform focus:outline-none focus:ring-2 focus:ring-purple-400"
        aria-label={open ? 'Close menu' : 'Open menu'}
        aria-expanded={open}
      >
  <LuLightbulb className={`text-2xl transition-transform ${open ? 'rotate-12' : ''}`} />
      </button>
    </div>
  );
}

FloatingActionMenu.propTypes = {
  onRefresh: PropTypes.func,
  onToggleCodex: PropTypes.func,
  onToggleInsights: PropTypes.func,
  onToggleSentiment: PropTypes.func,
  onToggleLearn: PropTypes.func,
  disabled: PropTypes.shape({
    refresh: PropTypes.bool,
    codex: PropTypes.bool,
    insights: PropTypes.bool,
    sentiment: PropTypes.bool,
    learn: PropTypes.bool,
  })
};
