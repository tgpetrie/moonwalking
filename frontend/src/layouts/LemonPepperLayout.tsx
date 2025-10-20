import React from "react";

export default function LemonPepperLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-dvh bg-black text-white antialiased">
      <header className="py-8">
        <div className="mx-auto max-w-6xl text-center">
          <h1 className="font-prosto text-4xl leading-tight tracking-tight">BHABIT</h1>
          <p className="mt-2 font-raleway text-sm opacity-80">Profits Buy Impulse</p>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4">{children}</main>
    </div>
  );
}
