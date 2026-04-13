import { Framework, WidgetConfig } from "../types";
import {
  buildConfigObject,
  buildJsObjectString,
  jsStr,
} from "./buildConfigObject";

interface TemplateParams {
  baseUrl: string;
  username: string;
  config: WidgetConfig;
}

export function getBubbleTemplate(
  framework: Framework,
  { baseUrl, username, config }: TemplateParams,
): string {
  const quote = framework === "vue" || framework === "astro" ? "'" : '"';
  const customConfig = buildConfigObject(config, quote, 3);

  // Build the main widget config object
  const widgetConfig = {
    mode: "bubble",
    expertUsername: username,
    personaName: config.personaName, // undefined will be skipped
    widgetToken: config.widgetToken || "YOUR_WIDGET_TOKEN",
    position: config.position,
    primaryColor: config.primaryColor,
    bubbleText: config.bubbleText,
    enableVoice: config.enableVoice,
    welcomeMessage: config.welcomeMessage,
  };
  const configString = buildJsObjectString(widgetConfig, quote, 3);

  switch (framework) {
    case "html":
      return `<!-- MyClone Widget -->
<script>
  (function() {
    var config = {
${configString}${customConfig}
    };

    function initWidget() {
      if (window.MyClone) {
        window.MyClone(config);
      }
    }

    var existingScript = document.querySelector('script[src*="myclone-embed.js"]');
    if (existingScript) {
      initWidget();
      return;
    }

    var script = document.createElement('script');
    script.src = ${jsStr(baseUrl, quote)} + '/embed/myclone-embed.js';
    script.async = true;
    script.onload = initWidget;
    script.onerror = function() {
      console.error('Failed to load MyClone widget');
    };
    document.body.appendChild(script);
  })();
</script>`;

    case "hostinger":
      return `<!-- MyClone Widget for Hostinger (Horizon) -->
<!-- Open your index.html file in Horizon -->
<!-- Find the closing </body> tag and paste this code right before it -->

<script>
  (function() {
    var config = {
${configString}${customConfig}
    };

    function initWidget() {
      if (window.MyClone) {
        window.MyClone(config);
      }
    }

    var existingScript = document.querySelector('script[src*="myclone-embed.js"]');
    if (existingScript) {
      initWidget();
      return;
    }

    var script = document.createElement('script');
    script.src = ${jsStr(baseUrl, quote)} + '/embed/myclone-embed.js';
    script.async = true;
    script.onload = initWidget;
    script.onerror = function() {
      console.error('Failed to load MyClone widget');
    };
    document.body.appendChild(script);
  })();
</script>`;

    case "nextjs": {
      // For Next.js, we use environment variable for token
      const nextjsConfig = {
        ...widgetConfig,
        widgetToken: undefined, // Will be replaced with env var
      };
      const nextjsConfigStr = buildJsObjectString(nextjsConfig, quote);

      return `// src/components/MyCloneWidget.tsx
"use client";

import Script from "next/script";

export function MyCloneWidget() {
  return (
    <Script
      src={${jsStr(baseUrl, quote)} + "/embed/myclone-embed.js"}
      strategy="afterInteractive"
      onLoad={() => {
        if (window.MyClone) {
          window.MyClone({
${nextjsConfigStr},
            widgetToken: process.env.NEXT_PUBLIC_CONVOXAI_TOKEN!${customConfig}
          });
        }
      }}
    />
  );
}

// app/layout.tsx
import { MyCloneWidget } from "@/components/MyCloneWidget";

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        {children}
        <MyCloneWidget />
      </body>
    </html>
  );
}

// .env.local
// NEXT_PUBLIC_CONVOXAI_TOKEN=your-widget-token`;
    }

    case "react": {
      // For React, we use Vite env variable for token
      const reactConfig = {
        ...widgetConfig,
        widgetToken: undefined, // Will be replaced with env var
      };
      const reactConfigStr = buildJsObjectString(reactConfig, quote);

      return `// src/components/MyCloneWidget.tsx
import { useEffect } from "react";

// TypeScript declarations
interface MyCloneWidgetConfig {
  expertUsername: string;
  widgetToken?: string;
  position?: "bottom-right" | "bottom-left" | "top-right" | "top-left";
  primaryColor?: string;
  bubbleText?: string;
  enableVoice?: boolean;
  welcomeMessage?: string;
}

interface MyCloneWidgetInstance {
  open: () => Promise<void>;
  close: () => Promise<void>;
  toggle: () => Promise<void>;
  destroy: () => void;
}

declare global {
  interface Window {
    MyClone?: (config: MyCloneWidgetConfig) => MyCloneWidgetInstance;
  }
}

export function MyCloneWidget() {
  useEffect(() => {
    let widget: MyCloneWidgetInstance | undefined;

    const script = document.createElement("script");
    script.src = ${jsStr(baseUrl, quote)} + "/embed/myclone-embed.js";
    script.async = true;

    script.onload = () => {
      if (window.MyClone) {
        widget = window.MyClone({
${reactConfigStr},
          widgetToken: import.meta.env.VITE_CONVOXAI_TOKEN${customConfig}
        });
      }
    };

    document.body.appendChild(script);

    return () => {
      widget?.destroy();
      if (script.parentNode) {
        document.body.removeChild(script);
      }
    };
  }, []);

  return null;
}

// App.tsx
import { MyCloneWidget } from "./components/MyCloneWidget";

function App() {
  return (
    <div className="App">
      <h1>Your App</h1>
      <MyCloneWidget />
    </div>
  );
}

// .env (Vite/Create React App)
// VITE_CONVOXAI_TOKEN=your-widget-token`;
    }

    case "react-js": {
      // For React JS, we use Vite env variable for token
      const reactJsConfig = {
        ...widgetConfig,
        widgetToken: undefined, // Will be replaced with env var
      };
      const reactJsConfigStr = buildJsObjectString(reactJsConfig, quote);

      return `// src/components/MyCloneWidget.jsx
import { useEffect } from "react";

export function MyCloneWidget() {
  useEffect(() => {
    let widget;

    const script = document.createElement("script");
    script.src = ${jsStr(baseUrl, quote)} + "/embed/myclone-embed.js";
    script.async = true;

    script.onload = () => {
      if (window.MyClone) {
        widget = window.MyClone({
${reactJsConfigStr},
          widgetToken: import.meta.env.VITE_CONVOXAI_TOKEN${customConfig}
        });
      }
    };

    document.body.appendChild(script);

    return () => {
      widget?.destroy();
      if (script.parentNode) {
        document.body.removeChild(script);
      }
    };
  }, []);

  return null;
}

// App.jsx
import { MyCloneWidget } from "./components/MyCloneWidget";

function App() {
  return (
    <div className="App">
      <h1>Your App</h1>
      <MyCloneWidget />
    </div>
  );
}

// .env (Vite/Create React App)
// VITE_CONVOXAI_TOKEN=your-widget-token`;
    }

    case "vue":
      return `<!-- App.vue -->
<template>
  <div id="app">
    <h1>Your App</h1>
  </div>
</template>

<script>
export default {
  name: 'App',
  data() {
    return {
      widget: null
    }
  },
  mounted() {
    const script = document.createElement('script');
    script.src = ${jsStr(baseUrl, quote)} + '/embed/myclone-embed.js';
    script.onload = () => {
      if (window.MyClone) {
        this.widget = window.MyClone({
${configString}${customConfig}
        });
      }
    };
    document.body.appendChild(script);
  },
  beforeUnmount() {
    if (this.widget) {
      this.widget.destroy();
    }
  }
}
</script>`;

    case "astro":
      return `<!-- src/components/MyCloneWidget.astro -->
---
// Widget configuration
---

<script is:inline>
  (function() {
    const script = document.createElement('script');
    script.src = ${jsStr(baseUrl, quote)} + '/embed/myclone-embed.js';

    script.onload = function() {
      if (window.MyClone) {
        window.MyClone({
${configString}${customConfig}
        });
      }
    };

    document.head.appendChild(script);
  })();
</script>

<!-- src/layouts/Layout.astro -->
<!--
---
import MyCloneWidget from "../components/MyCloneWidget.astro";
---

<!doctype html>
<html lang="en">
  <body>
    <slot />
    <MyCloneWidget />
  </body>
</html>
-->`;

    case "wordpress":
    case "wix":
      return `<!-- MyClone Widget - Add to footer before closing </div> or </body> tag -->
<script>
  (function() {
    var config = {
${configString}${customConfig}
    };

    var existingScript = document.querySelector('script[src*="myclone-embed.js"]');
    if (existingScript) {
      if (window.MyClone) {
        window.MyClone(config);
      }
      return;
    }

    var script = document.createElement('script');
    script.src = ${jsStr(baseUrl, quote)} + '/embed/myclone-embed.js';
    script.async = true;
    script.onload = function() {
      if (window.MyClone) {
        window.MyClone(config);
      }
    };
    script.onerror = function() {
      console.error('Failed to load MyClone widget');
    };

    if (document.body) {
      document.body.appendChild(script);
    } else {
      document.addEventListener('DOMContentLoaded', function() {
        document.body.appendChild(script);
      });
    }
  })();
</script>`;

    default:
      return `<!-- ${framework} code coming soon -->`;
  }
}
