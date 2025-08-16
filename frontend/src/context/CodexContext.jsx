import React, { createContext, useContext, useRef, useState } from 'react';

const CodexContext = createContext(null);

export const useCodex = () => {
  const ctx = useContext(CodexContext);
  if (!ctx) throw new Error('useCodex must be used within CodexProvider');
  return ctx;
};

export const CodexProvider = ({ children }) => {
  const logsRef = useRef([]);
  const lastPctRef = useRef({});
  const trendRef = useRef({});
  const [logs, setLogs] = useState([]);

  const appendLog = (symbol, reason, value) => {
    const entry = { ts: Date.now(), symbol, reason, value };
    logsRef.current.push(entry);
    if (logsRef.current.length > 100) {
      logsRef.current = logsRef.current.slice(-100);
    }
    setLogs([...logsRef.current]);
  };

  const process = (symbol, pct, opts = {}) => {
    const minDelta = typeof opts.minDeltaToUpdate === 'number' ? opts.minDeltaToUpdate : 0.1;
    const trendWindow = typeof opts.trendWindow === 'number' ? opts.trendWindow : 5;

    const last = lastPctRef.current[symbol] ?? 0;
    const delta = Math.abs(pct - last);
    if (delta < minDelta) {
      appendLog(symbol, 'minDeltaToUpdate', delta.toFixed(4));
      return { shouldUpdate: false, trendScore: trendRef.current[symbol]?.score || 0 };
    }

    lastPctRef.current[symbol] = pct;

    const arr = trendRef.current[symbol]?.arr || [];
    arr.push(pct);
    if (arr.length > trendWindow) arr.shift();
    const score = arr.reduce((a, b) => a + b, 0);
    trendRef.current[symbol] = { arr, score };
    appendLog(symbol, 'update', pct.toFixed(4));
    return { shouldUpdate: true, trendScore: score };
  };

  const contextValue = {
    process,
    logs,
  };

  return (
    <CodexContext.Provider value={contextValue}>
      {children}
    </CodexContext.Provider>
  );
};

export default CodexContext;
