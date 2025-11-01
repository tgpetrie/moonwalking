import React from "react";
import ReactDOM from "react-dom/client";
import "./index.css";
import Dashboard from "./components/Dashboard.jsx";

const root = document.getElementById("root") || (() => {
  const el = document.createElement("div");
  el.id = "root";
  document.body.appendChild(el);
  return el;
})();

ReactDOM.createRoot(root).render(
  <React.StrictMode>
    <Dashboard />
  </React.StrictMode>
);
