import React from "react";
import ReactDOM from "react-dom/client";
import VitalFrontend from "./App.jsx";  // ✅ note .jsx

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <VitalFrontend />
  </React.StrictMode>
);
