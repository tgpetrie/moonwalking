import React from "react";

/** Small swatch card */
function Swatch({ name, hex, usage, textClass = "text-lock-white" }) {
  return (
    <div className="rounded-2xl p-4 ring-1 ring-white/10 bg-[#0A0A0D]">
      <div className="h-20 w-full rounded-xl" style={{ backgroundColor: hex }} />
      <div className="mt-3 flex items-baseline justify-between">
        <div className="text-sm text-lock-white/70">{name}</div>
        <div className="text-xs text-lock-white/50">{usage}</div>
      </div>
      <div className="mt-1 font-mono text-xs text-lock-white/70">{hex}</div>
      <div className="mt-3 rounded-lg p-3" style={{ backgroundColor: hex }}>
        <div className="text-sm font-semibold">
          <span className={textClass}>123.45%</span>
          <span className="mx-2"> • </span>
          <span className={textClass}>+2.47%</span>
        </div>
      </div>
    </div>
  );
}

export default function DesignColors() {
  return (
    <div className="min-h-screen bg-lock-black text-lock-white">
      <div className="mx-auto max-w-6xl px-6 py-10">
        <h1 className="text-2xl font-bold tracking-tight">BHABIT Locked Palette — Live Preview</h1>
        <p className="mt-2 text-sm text-lock-white/70">
          Unified purple: <span className="font-mono">#8B5CF6</span>. Price accents available as Aqua (<span className="font-mono">#22D3EE</span>) and Teal (<span className="font-mono">#2DD4BF</span>).
        </p>

        {/* Swatches */}
        <div className="mt-8 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
          <Swatch name="BH Purple" hex="#8B5CF6" usage="Brand / CTAs / Chips" textClass="text-lock-white" />
          <Swatch name="BH Orange" hex="#FB923C" usage="Accents / Alerts" textClass="text-lock-white" />
          <Swatch name="BH Pink"   hex="#F472B6" usage="Losers / Down Moves" textClass="text-lock-white" />
          <Swatch name="BH Aqua"   hex="#22D3EE" usage="Prices (pop/neon)" textClass="text-lock-black" />
          <Swatch name="BH Teal"   hex="#2DD4BF" usage="Prices (soft/teal)" textClass="text-lock-black" />
          <Swatch name="BH White"  hex="#F7F7F9" usage="Primary text" textClass="text-lock-black" />
        </div>

        {/* Real component-ish preview */}
        <div className="mt-10 grid grid-cols-1 gap-6 lg:grid-cols-2">
          <div className="rounded-2xl border border-white/10 bg-[#0F0F13] p-5">
            <div className="text-sm uppercase tracking-widest text-lock-white/60">Table / Gainers (Aqua)</div>
            <div className="mt-3 divide-y divide-white/5">
              {["SOL-USD","ARB-USD","RUNE-USD","OP-USD","TIA-USD"].map((s,i)=>(
                <div key={s} className="flex items-center justify-between py-2">
                  <div className="text-lock-white">{i+1}. {s}</div>
                  <div className="text-lock-aqua">+{(Math.random()*5+1).toFixed(2)}%</div>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-2xl border border-white/10 bg-[#0F0F13] p-5">
            <div className="text-sm uppercase tracking-widest text-lock-white/60">Table / Gainers (Teal)</div>
            <div className="mt-3 divide-y divide-white/5">
              {["SOL-USD","ARB-USD","RUNE-USD","OP-USD","TIA-USD"].map((s,i)=>(
                <div key={s} className="flex items-center justify-between py-2">
                  <div className="text-lock-white">{i+1}. {s}</div>
                  <div className="text-lock-teal">+{(Math.random()*5+1).toFixed(2)}%</div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Buttons w/ purple lock */}
        <div className="mt-10 flex flex-wrap gap-3">
          <button className="rounded-xl bg-lock-purple px-4 py-2 text-sm font-medium text-lock-white">
            Primary (Purple)
          </button>
          <button className="rounded-xl border border-lock-purple/60 px-4 py-2 text-sm font-medium text-lock-white/80">
            Ghost (Purple Border)
          </button>
          <button className="rounded-xl bg-gradient-to-r from-lock-purple to-lock-purple px-4 py-2 text-sm font-medium text-lock-white/90">
            Gradient (Locked Purple)
          </button>
        </div>
      </div>
    </div>
  );
}