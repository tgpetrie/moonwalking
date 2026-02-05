import React from "react";
import ReactDOM from "react-dom/client";
import "./index.css";
import "./styles/info-modal.css";
import App from "./App.jsx";
import { SentimentProvider } from "./context/SentimentContext.jsx";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <SentimentProvider>
      <App />
    </SentimentProvider>
  </React.StrictMode>
);
