/**
 * ConvoxAI Embed App Entry Point
 * React app that runs inside the iframe
 */

import React from "react";
import ReactDOM from "react-dom/client";
import { EmbedApp } from "./EmbedApp";
import "../styles/globals-embed.css"; // Import Tailwind CSS (Preflight disabled)
import "../styles/embed.css";

// Get root element
const rootElement = document.getElementById("root");

if (!rootElement) {
  throw new Error("Root element not found");
}

// Create React root and render app
const root = ReactDOM.createRoot(rootElement);

// Note: StrictMode removed to prevent double mounting issues when parent app also uses StrictMode
root.render(<EmbedApp />);
