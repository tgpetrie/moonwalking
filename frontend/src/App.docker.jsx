import React, { useEffect, useState } from "react";
import '../index.css';
import logobro from './logobro.png';

// ...existing code from App.jsx...

export default function App() {
  // ...existing code...
}

// CountdownTimer component for global timer
function CountdownTimer() {
  const [secondsLeft, setSecondsLeft] = React.useState(29);
  React.useEffect(() => {
    const interval = setInterval(() => {
      setSecondsLeft((prev) => (prev > 0 ? prev - 1 : 29));
    }, 1000);
    return () => clearInterval(interval);
  }, []);
  return <span>{secondsLeft}</span>;
}
