import React, { useState } from 'react';
import CodexDebugPanel from './CodexDebugPanel';

export default function CodexToggle() {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ position: 'fixed', bottom: 12, right: 12, zIndex: 60 }}>
      <button
        onClick={() => setOpen(o => !o)}
        className="px-3 py-1 rounded bg-purple-600/80 hover:bg-purple-500 text-white text-xs shadow"
      >
        {open ? 'Close Codex' : 'Codex Logs'}
      </button>
      {open && (
        <div className="mt-2 w-[380px]">
          <CodexDebugPanel />
        </div>
      )}
    </div>
  );
}
