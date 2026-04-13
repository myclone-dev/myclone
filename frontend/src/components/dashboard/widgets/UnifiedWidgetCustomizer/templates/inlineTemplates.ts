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

export function getInlineTemplate(
  framework: Framework,
  { baseUrl, username, config }: TemplateParams,
): string {
  const quote = framework === "vue" || framework === "astro" ? "'" : '"';
  const customConfig = buildConfigObject(config, quote, 3);

  // Build the main widget config object for inline mode
  const widgetConfig = {
    mode: "inline",
    container: "#myclone-chat",
    height: config.height,
    expertUsername: username,
    personaName: config.personaName, // undefined will be skipped
    widgetToken: config.widgetToken || "YOUR_WIDGET_TOKEN",
    primaryColor: config.primaryColor,
    enableVoice: config.enableVoice,
  };
  const configString = buildJsObjectString(widgetConfig, quote);

  switch (framework) {
    case "html":
      return `<!-- MyClone Inline Widget -->
<!-- 1. Add container where you want the chat -->
<div id="myclone-chat"></div>

<!-- 2. Load widget script -->
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
      return `<!-- MyClone Inline Widget for Hostinger (Horizon) -->
<!-- Open your index.html file in Horizon -->
<!-- 1. Add container where you want the chat -->
<div id="myclone-chat"></div>

<!-- 2. Find the closing </body> tag and paste this code right before it -->
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
      // For Next.js, use environment variable for token
      const nextjsConfig = {
        ...widgetConfig,
        container: "#myclone-chat",
        widgetToken: undefined, // Will be replaced with env var
      };
      const nextjsConfigStr = buildJsObjectString(nextjsConfig, quote);

      return `// src/components/MyCloneInlineWidget.tsx
"use client";

import Script from "next/script";

export function MyCloneInlineWidget() {
  return (
    <>
      {/* Container for inline widget */}
      <div id="myclone-chat" className="w-full h-[${jsStr(config.height, quote)}]"></div>

      <Script
        src={${jsStr(baseUrl, quote)} + "/embed/myclone-embed.js"}
        strategy="lazyOnload"
        onLoad={() => {
          if (window.MyClone) {
            window.MyClone({
${nextjsConfigStr},
              widgetToken: process.env.NEXT_PUBLIC_CONVOXAI_TOKEN!${customConfig}
            });
          }
        }}
      />
    </>
  );
}

// app/contact/page.tsx (or any page)
import { MyCloneInlineWidget } from "@/components/MyCloneInlineWidget";

export default function ContactPage() {
  return (
    <div className="container mx-auto py-12">
      <h1 className="text-3xl font-bold mb-8">Contact Us</h1>
      <MyCloneInlineWidget />
    </div>
  );
}

// .env.local
// NEXT_PUBLIC_CONVOXAI_TOKEN=your-widget-token`;
    }

    case "react": {
      // For React, use Vite env variable for token
      const reactConfig = {
        ...widgetConfig,
        container: "#myclone-inline-chat",
        widgetToken: undefined, // Will be replaced with env var
      };
      const reactConfigStr = buildJsObjectString(reactConfig, quote);

      return `// src/components/MyCloneInlineWidget.tsx
import { useEffect, useRef } from "react";

interface MyCloneWidgetConfig {
  mode: "inline";
  container: string;
  height: string;
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

export function MyCloneInlineWidget() {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let widget: MyCloneWidgetInstance | undefined;

    const initWidget = () => {
      if (window.MyClone && containerRef.current) {
        widget = window.MyClone({
${reactConfigStr},
          widgetToken: import.meta.env.VITE_CONVOXAI_TOKEN${customConfig}
        });
      }
    };

    const script = document.createElement("script");
    script.src = ${jsStr(baseUrl, quote)} + "/embed/myclone-embed.js";
    script.async = true;
    script.onload = initWidget;
    document.body.appendChild(script);

    return () => {
      widget?.destroy();
      if (script.parentNode) {
        document.body.removeChild(script);
      }
    };
  }, []);

  return (
    <div
      ref={containerRef}
      id="myclone-inline-chat"
      style={{ width: "100%", height: ${jsStr(config.height, quote)} }}
    />
  );
}

// App.tsx
import { MyCloneInlineWidget } from "./components/MyCloneInlineWidget";

function App() {
  return (
    <div className="container mx-auto py-12">
      <h1>Contact Us</h1>
      <MyCloneInlineWidget />
    </div>
  );
}

// .env
// VITE_CONVOXAI_TOKEN=your-widget-token`;
    }

    case "react-js": {
      // For React JS, use Vite env variable for token
      const reactJsConfig = {
        ...widgetConfig,
        container: "#myclone-inline-chat",
        widgetToken: undefined,
      };
      const reactJsConfigStr = buildJsObjectString(reactJsConfig, quote);

      return `// src/components/MyCloneInlineWidget.jsx
import { useEffect, useRef } from "react";

export function MyCloneInlineWidget() {
  const containerRef = useRef(null);

  useEffect(() => {
    let widget;

    const initWidget = () => {
      if (window.MyClone && containerRef.current) {
        widget = window.MyClone({
${reactJsConfigStr},
          widgetToken: import.meta.env.VITE_CONVOXAI_TOKEN${customConfig}
        });
      }
    };

    const script = document.createElement("script");
    script.src = ${jsStr(baseUrl, quote)} + "/embed/myclone-embed.js";
    script.async = true;
    script.onload = initWidget;
    document.body.appendChild(script);

    return () => {
      widget?.destroy();
      if (script.parentNode) {
        document.body.removeChild(script);
      }
    };
  }, []);

  return (
    <div
      ref={containerRef}
      id="myclone-inline-chat"
      style={{ width: "100%", height: ${jsStr(config.height, quote)} }}
    />
  );
}

// App.jsx
import { MyCloneInlineWidget } from "./components/MyCloneInlineWidget";

function App() {
  return (
    <div className="container mx-auto py-12">
      <h1>Contact Us</h1>
      <MyCloneInlineWidget />
    </div>
  );
}

// .env
// VITE_CONVOXAI_TOKEN=your-widget-token`;
    }

    case "vue": {
      const vueConfig = {
        ...widgetConfig,
        container: "#myclone-inline-chat",
      };
      const vueConfigStr = buildJsObjectString(vueConfig, quote);

      return `<!-- MyCloneInlineWidget.vue -->
<template>
  <div
    id="myclone-inline-chat"
    ref="container"
    :style="{ width: '100%', height: ${jsStr(config.height, quote)} }"
  />
</template>

<script>
export default {
  name: 'MyCloneInlineWidget',
  data() {
    return {
      widget: null
    }
  },
  mounted() {
    const initWidget = () => {
      if (window.MyClone) {
        this.widget = window.MyClone({
${vueConfigStr}${customConfig}
        });
      }
    };

    const script = document.createElement('script');
    script.src = ${jsStr(baseUrl, quote)} + '/embed/myclone-embed.js';
    script.onload = initWidget;
    document.body.appendChild(script);
  },
  beforeUnmount() {
    if (this.widget) {
      this.widget.destroy();
    }
  }
}
</script>

<!-- App.vue -->
<template>
  <div id="app" class="container mx-auto py-12">
    <h1 class="text-3xl font-bold mb-8">Contact Us</h1>
    <MyCloneInlineWidget />
  </div>
</template>

<script>
import MyCloneInlineWidget from './components/MyCloneInlineWidget.vue'

export default {
  name: 'App',
  components: {
    MyCloneInlineWidget
  }
}
</script>`;
    }

    case "astro": {
      const astroConfig = {
        ...widgetConfig,
        container: "#myclone-inline-chat",
      };
      const astroConfigStr = buildJsObjectString(astroConfig, quote);

      return `<!-- src/components/MyCloneInlineWidget.astro -->
---
const containerId = "myclone-inline-chat";
---

<div id={containerId} style="width: 100%; height: ${jsStr(config.height, quote)};"></div>

<script is:inline define:vars={{ containerId }}>
  (function() {
    const initWidget = () => {
      if (window.MyClone) {
        window.MyClone({
${astroConfigStr.replace(/"/g, '\\"')}${customConfig}
        });
      }
    };

    const script = document.createElement('script');
    script.src = ${jsStr(baseUrl, quote)} + '/embed/myclone-embed.js';
    script.onload = initWidget;
    document.head.appendChild(script);
  })();
</script>

<!-- src/pages/contact.astro -->
<!--
---
import Layout from "../layouts/Layout.astro";
import MyCloneInlineWidget from "../components/MyCloneInlineWidget.astro";
---

<Layout title="Contact Us">
  <main class="container mx-auto py-12">
    <h1 class="text-3xl font-bold mb-8">Contact Us</h1>
    <MyCloneInlineWidget />
  </main>
</Layout>
-->`;
    }

    case "wordpress":
    case "wix": {
      const wpConfig = {
        ...widgetConfig,
        container: "#myclone-inline-chat",
      };
      const wpConfigStr = buildJsObjectString(wpConfig, quote);

      return `<!-- MyClone Inline Widget -->
<!-- 1. Add container where you want the chat -->
<div id="myclone-inline-chat" style="width: 100%; height: ${jsStr(config.height, quote)};"></div>

<!-- 2. Add this script to Custom Code -->
<script>
  (function() {
    var config = {
${wpConfigStr}${customConfig}
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
</script>`;
    }

    default:
      return `<!-- Inline mode example for ${framework} coming soon -->`;
  }
}
