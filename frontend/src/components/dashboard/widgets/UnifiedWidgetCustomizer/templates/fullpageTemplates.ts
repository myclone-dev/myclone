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

export function getFullpageTemplate(
  framework: Framework,
  { baseUrl, username, config }: TemplateParams,
): string {
  const quote = framework === "vue" || framework === "astro" ? "'" : '"';
  const customConfig = buildConfigObject(config, quote, 3);

  // Build the main widget config object for fullpage mode
  const widgetConfig = {
    mode: "fullpage",
    expertUsername: username,
    personaName: config.personaName, // undefined will be skipped
    widgetToken: config.widgetToken || "YOUR_WIDGET_TOKEN",
    primaryColor: config.primaryColor,
    enableVoice: config.enableVoice,
  };
  const configString = buildJsObjectString(widgetConfig, quote);

  switch (framework) {
    case "html":
      return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Chat with ${jsStr(username, quote)}</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    html, body { height: 100%; width: 100%; }
  </style>
</head>
<body>
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
  </script>
</body>
</html>`;

    case "hostinger":
      return `<!-- MyClone Fullpage Widget for Hostinger (Horizon) -->
<!-- Replace your entire index.html content with this -->
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Chat with ${jsStr(username, quote)}</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    html, body { height: 100%; width: 100%; }
  </style>
</head>
<body>
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
  </script>
</body>
</html>`;

    case "nextjs": {
      const nextjsConfig = {
        ...widgetConfig,
        widgetToken: undefined,
      };
      const nextjsConfigStr = buildJsObjectString(nextjsConfig, quote);

      return `// src/app/chat/page.tsx (dedicated chat page)
"use client";

import Script from "next/script";
import { useEffect, useState } from "react";

export default function ChatPage() {
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (loaded && window.MyClone) {
      window.MyClone({
${nextjsConfigStr},
        widgetToken: process.env.NEXT_PUBLIC_CONVOXAI_TOKEN!${customConfig}
      });
    }
  }, [loaded]);

  return (
    <Script
      src={${jsStr(baseUrl, quote)} + "/embed/myclone-embed.js"}
      strategy="afterInteractive"
      onLoad={() => setLoaded(true)}
    />
  );
}

// src/app/chat/layout.tsx (optional: minimal layout for fullpage)
export default function ChatLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body style={{ margin: 0, padding: 0 }}>{children}</body>
    </html>
  );
}

// .env.local
// NEXT_PUBLIC_CONVOXAI_TOKEN=your-widget-token`;
    }

    case "react": {
      const reactConfig = {
        ...widgetConfig,
        widgetToken: undefined,
      };
      const reactConfigStr = buildJsObjectString(reactConfig, quote);

      return `// src/pages/ChatPage.tsx
import { useEffect } from "react";

interface MyCloneWidgetConfig {
  mode: "fullpage";
  expertUsername: string;
  widgetToken?: string;
  primaryColor?: string;
  enableVoice?: boolean;
}

interface MyCloneWidgetInstance {
  destroy: () => void;
}

declare global {
  interface Window {
    MyClone?: (config: MyCloneWidgetConfig) => MyCloneWidgetInstance;
  }
}

export function ChatPage() {
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

  return null; // Widget takes over the entire page
}

// App.tsx (with React Router)
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { ChatPage } from "./pages/ChatPage";
import { HomePage } from "./pages/HomePage";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/chat" element={<ChatPage />} />
      </Routes>
    </BrowserRouter>
  );
}

// .env
// VITE_CONVOXAI_TOKEN=your-widget-token`;
    }

    case "react-js": {
      const reactJsConfig = {
        ...widgetConfig,
        widgetToken: undefined,
      };
      const reactJsConfigStr = buildJsObjectString(reactJsConfig, quote);

      return `// src/pages/ChatPage.jsx
import { useEffect } from "react";

export function ChatPage() {
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

  return null; // Widget takes over the entire page
}

// App.jsx (with React Router)
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { ChatPage } from "./pages/ChatPage";
import { HomePage } from "./pages/HomePage";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/chat" element={<ChatPage />} />
      </Routes>
    </BrowserRouter>
  );
}

// .env
// VITE_CONVOXAI_TOKEN=your-widget-token`;
    }

    case "vue":
      return `<!-- src/views/ChatPage.vue -->
<template>
  <!-- Widget takes over entire page, no template needed -->
</template>

<script>
export default {
  name: 'ChatPage',
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
</script>

<!-- router/index.js -->
<!--
import { createRouter, createWebHistory } from 'vue-router'
import HomePage from '../views/HomePage.vue'
import ChatPage from '../views/ChatPage.vue'

const routes = [
  { path: '/', component: HomePage },
  { path: '/chat', component: ChatPage }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
-->`;

    case "astro":
      return `<!-- src/pages/chat.astro -->
---
// Fullpage chat experience
---

<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Chat with ${jsStr(username, quote)}</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    html, body { height: 100%; width: 100%; }
  </style>
</head>
<body>
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
</body>
</html>`;

    case "wordpress":
    case "wix":
      return `<!-- Create a dedicated fullpage chat experience -->
<!-- WordPress: Create custom page template (page-chat.php) -->
<!-- Wix: Add to Settings > Custom Code > Header or use HTML element -->

<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Chat with ${jsStr(username, quote)}</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    html, body { height: 100%; width: 100%; overflow: hidden; }
  </style>
</head>
<body>
  <script>
    (function() {
      var config = {
${configString}${customConfig}
      };

      function loadWidget() {
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
      }

      if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', loadWidget);
      } else {
        loadWidget();
      }
    })();
  </script>
</body>
</html>`;

    default:
      return `<!-- Fullpage mode example for ${framework} coming soon -->`;
  }
}
