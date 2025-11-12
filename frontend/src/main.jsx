import React from "react";
import ReactDOM from "react-dom/client";
import "./index.css";
import AppRoot from "./AppRoot.jsx";
import { DataProvider } from "./context/DataContext.jsx";
import { WatchlistProvider } from "./context/WatchlistContext.jsx";
import { SentimentProvider } from "./context/SentimentContext.jsx";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <DataProvider>
      <SentimentProvider>
        <WatchlistProvider>
          <AppRoot />
        </WatchlistProvider>
      </SentimentProvider>
    </DataProvider>
  </React.StrictMode>
);
