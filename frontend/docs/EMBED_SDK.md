# MyClone Embed SDK - Complete Guide

> Embeddable chat widget for integrating MyClone AI experts into any website with a single script tag.

## Table of Contents

- [Quick Start](#quick-start)
- [Installation](#installation)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Session Management](#session-management)
- [Customization](#customization)
- [Advanced Usage](#advanced-usage)
- [Development](#development)
- [Troubleshooting](#troubleshooting)

---

## Quick Start

### 30-Second Integration

Add this to your website before `</body>`:

```html
<script src="https://app.myclone.com/embed/myclone-embed.js"></script>
<script>
  window.MyClone({
    expertUsername: "your-username",
    widgetToken: "your-widget-token", // Get from dashboard
    position: "bottom-right",
  });
</script>
```

**Get your credentials:**

1. Go to [Dashboard → Widgets → Tokens](https://app.myclone.com/dashboard/widgets)
2. Create a new token
3. Copy your `expertUsername` and `widgetToken`

That's it! The widget will appear in the bottom-right corner of your page.

---

## Installation

### Method 1: CDN (Recommended)

```html
<!-- Load the SDK -->
<script src="https://app.myclone.com/embed/myclone-embed.js"></script>

<!-- Initialize widget -->
<script>
  const widget = window.MyClone({
    expertUsername: "your-username",
    widgetToken: "your-widget-token",
    position: "bottom-right",
    primaryColor: "#6366f1",
    enableVoice: true,
  });
</script>
```

### Method 2: Self-Hosted

1. Download the SDK bundle:
   - `/embed/myclone-embed.js`
   - `/embed/app.html`
   - `/embed/assets/` (entire folder)

2. Upload to your server maintaining the folder structure

3. Load from your domain:

```html
<script src="/embed/myclone-embed.js"></script>
```

### Method 3: NPM Module (Coming Soon)

```bash
npm install @myclone/embed-sdk
```

---

## Framework Integration

### Next.js Integration

For Next.js applications (App Router), create a reusable widget component:

**src/components/MyCloneWidget.tsx:**

```tsx
"use client";

import Script from "next/script";

interface MyCloneWidgetProps {
  expertUsername: string;
  widgetToken: string;
  position?: "bottom-right" | "bottom-left" | "top-right" | "top-left";
  primaryColor?: string;
  bubbleText?: string;
  enableVoice?: boolean;
  welcomeMessage?: string;
}

export function MyCloneWidget({
  expertUsername,
  widgetToken,
  position = "bottom-right",
  primaryColor = "#6366f1",
  bubbleText = "Chat with me",
  enableVoice = false,
  welcomeMessage,
}: MyCloneWidgetProps) {
  return (
    <Script
      src="https://app.myclone.com/embed/myclone-embed.js"
      strategy="lazyOnload"
      onLoad={() => {
        if (typeof window !== "undefined" && window.MyClone) {
          window.MyClone({
            expertUsername,
            widgetToken,
            position,
            primaryColor,
            bubbleText,
            enableVoice,
            welcomeMessage,
          });
        }
      }}
      onError={(e) => {
        console.error("Failed to load MyClone widget:", e);
      }}
    />
  );
}

// TypeScript declaration
declare global {
  interface Window {
    MyClone?: (config: {
      expertUsername: string;
      widgetToken: string;
      position?: string;
      primaryColor?: string;
      bubbleText?: string;
      enableVoice?: boolean;
      welcomeMessage?: string;
    }) => void;
  }
}
```

**app/layout.tsx:**

```tsx
import { MyCloneWidget } from "@/components/MyCloneWidget";

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        {children}

        {/* Add widget to all pages */}
        <MyCloneWidget
          expertUsername={process.env.NEXT_PUBLIC_CONVOXAI_USERNAME!}
          widgetToken={process.env.NEXT_PUBLIC_CONVOXAI_TOKEN!}
          enableVoice={true}
        />
      </body>
    </html>
  );
}
```

**Environment variables (.env.local):**

```bash
NEXT_PUBLIC_CONVOXAI_USERNAME=your-username
NEXT_PUBLIC_CONVOXAI_TOKEN=your-widget-token
```

**Get your token:** [Dashboard → Widgets → Tokens](https://app.myclone.com/dashboard/widgets)

### React Integration (CRA/Vite)

For standard React applications:

**src/components/MyCloneWidget.tsx:**

```tsx
import { useEffect } from "react";

interface MyCloneWidgetProps {
  expertUsername: string;
  widgetToken: string;
  position?: string;
  primaryColor?: string;
  enableVoice?: boolean;
}

export function MyCloneWidget({
  expertUsername,
  widgetToken,
  position = "bottom-right",
  primaryColor = "#6366f1",
  enableVoice = false,
}: MyCloneWidgetProps) {
  useEffect(() => {
    const script = document.createElement("script");
    script.src = "https://app.myclone.com/embed/myclone-embed.js";
    script.async = true;

    script.onload = () => {
      if (window.MyClone) {
        window.MyClone({
          expertUsername,
          widgetToken,
          position,
          primaryColor,
          enableVoice,
        });
      }
    };

    document.body.appendChild(script);

    return () => {
      document.body.removeChild(script);
    };
  }, [expertUsername, widgetToken, position, primaryColor, enableVoice]);

  return null;
}

declare global {
  interface Window {
    MyClone?: (config: any) => void;
  }
}
```

**App.tsx:**

```tsx
import { MyCloneWidget } from "./components/MyCloneWidget";

function App() {
  return (
    <div className="App">
      <h1>Your Application</h1>

      <MyCloneWidget
        expertUsername="your-username"
        widgetToken="your-widget-token"
        enableVoice={true}
      />
    </div>
  );
}
```

### Vue Integration

```vue
<template>
  <div id="app">
    <!-- Your app content -->
  </div>
</template>

<script>
export default {
  name: "App",
  mounted() {
    const script = document.createElement("script");
    script.src = "https://app.myclone.com/embed/myclone-embed.js";
    script.onload = () => {
      window.MyClone({
        expertUsername: "your-username",
        widgetToken: "your-widget-token",
        enableVoice: true,
      });
    };
    document.body.appendChild(script);
  },
};
</script>
```

### WordPress Integration

Add this to your theme's `footer.php` or use a custom HTML widget:

```html
<script src="https://app.myclone.com/embed/myclone-embed.js"></script>
<script>
  window.MyClone({
    expertUsername: "your-username",
    widgetToken: "your-widget-token",
    position: "bottom-right",
    primaryColor: "#6366f1",
    enableVoice: true,
  });
</script>
```

Or use a plugin like "Insert Headers and Footers" to add the code.

### Webflow Integration

1. Go to Project Settings → Custom Code → Footer Code
2. Paste:

```html
<script src="https://app.myclone.com/embed/myclone-embed.js"></script>
<script>
  window.MyClone({
    expertUsername: "your-username",
    widgetToken: "your-widget-token",
    position: "bottom-right",
  });
</script>
```

3. Publish site

**Complete examples:**

- [Next.js Example](../src/embed/examples/nextjs-integration.tsx)
- [React Example](../src/embed/examples/react-integration.tsx)
- [Vanilla HTML Example](../src/embed/examples/vanilla-html.html)

---

## Configuration

### Basic Configuration

```javascript
window.MyClone({
  // REQUIRED
  expertUsername: "johndoe", // Expert's username
  widgetToken: "wgt_xxxxx", // Widget authentication token (get from dashboard)

  // OPTIONAL - Positioning
  position: "bottom-right", // bottom-right | bottom-left | top-right | top-left

  // OPTIONAL - Appearance
  primaryColor: "#6366f1", // Brand color (hex)
  bubbleText: "Chat with me", // Bubble button text
  bubbleIcon: "https://...", // Custom icon URL

  // OPTIONAL - Features
  enableVoice: true, // Enable voice chat
  welcomeMessage: "Hi! How can I help?",
  inputPlaceholder: "Type a message...",

  // OPTIONAL - User context
  user: {
    email: "user@example.com",
    name: "John Doe",
    // Custom metadata
    company: "Acme Corp",
    plan: "enterprise",
  },

  // OPTIONAL - Custom styling
  customCss: `.embed-bubble { border-radius: 12px; }`,

  // OPTIONAL - Callbacks
  onOpen: () => console.log("Widget opened"),
  onClose: () => console.log("Widget closed"),
  onMessage: (message) => console.log("User sent:", message),
  onEmailSubmit: (email) => console.log("Email collected:", email),
  onError: (error) => console.error("Widget error:", error),
});
```

### Configuration Options

| Option                 | Type       | Default                  | Description                                                            |
| ---------------------- | ---------- | ------------------------ | ---------------------------------------------------------------------- |
| `expertUsername`       | `string`   | **required**             | Username of the expert to chat with                                    |
| `widgetToken`          | `string`   | **required**             | Widget authentication token (from dashboard)                           |
| `position`             | `string`   | `"bottom-right"`         | Bubble button position on screen                                       |
| `primaryColor`         | `string`   | `"#6366f1"`              | Brand color (hex format)                                               |
| `bubbleText`           | `string`   | `"Chat with me"`         | Text on bubble button                                                  |
| `bubbleIcon`           | `string`   | `undefined`              | Custom icon URL                                                        |
| `enableVoice`          | `boolean`  | `false`                  | Enable voice chat feature                                              |
| `welcomeMessage`       | `string`   | `undefined`              | Initial greeting message                                               |
| `inputPlaceholder`     | `string`   | `"Type your message..."` | Input field placeholder                                                |
| `user`                 | `object`   | `undefined`              | Pre-fill user information                                              |
| `customCss`            | `string`   | `undefined`              | Custom CSS overrides                                                   |
| `zIndex`               | `number`   | `999999`                 | Z-index for widget                                                     |
| `layout.modalPosition` | `string`   | `undefined` (centered)   | Modal position: "bottom-right", "bottom-left", "top-right", "top-left" |
| `layout.position`      | `string`   | `"bottom-right"`         | Bubble button position (same as `position`)                            |
| `layout.offsetX`       | `string`   | `"20px"`                 | Horizontal offset from edge                                            |
| `layout.offsetY`       | `string`   | `"20px"`                 | Vertical offset from edge                                              |
| `onOpen`               | `function` | `undefined`              | Called when widget opens                                               |
| `onClose`              | `function` | `undefined`              | Called when widget closes                                              |
| `onMessage`            | `function` | `undefined`              | Called when user sends message                                         |
| `onEmailSubmit`        | `function` | `undefined`              | Called when email captured                                             |
| `onError`              | `function` | `undefined`              | Called on errors                                                       |

**Get your widget token:** [Dashboard → Widgets → Tokens](https://app.myclone.com/dashboard/widgets)

---

## API Reference

### Widget Methods

The `MyClone()` function returns a widget instance with these methods:

```javascript
const widget = window.MyClone({ expertUsername: "johndoe" });

// Programmatically open the widget
await widget.open();

// Programmatically close the widget
await widget.close();

// Toggle widget state
await widget.toggle();

// Update user information
await widget.setUser({
  email: "newemail@example.com",
  name: "Jane Doe",
});

// Check if widget is expanded
const isOpen = await widget.isExpanded();

// Destroy widget (remove from page)
widget.destroy();
```

### Events & Callbacks

#### onOpen

Called when the widget is opened (either by user click or programmatically).

```javascript
onOpen: () => {
  console.log("Widget opened");
  // Track analytics
  analytics.track("Widget Opened");
};
```

#### onClose

Called when the widget is closed.

```javascript
onClose: () => {
  console.log("Widget closed");
};
```

#### onMessage

Called when the user sends a message.

```javascript
onMessage: (message) => {
  console.log("User message:", message);
  // Send to your analytics
  analytics.track("Message Sent", { message });
};
```

#### onEmailSubmit

Called when the user submits their email (triggered after 2+ messages).

```javascript
onEmailSubmit: (email) => {
  console.log("Email captured:", email);
  // Add to your CRM
  crm.addContact({ email });
};
```

#### onError

Called when an error occurs.

```javascript
onError: (error) => {
  console.error("Widget error:", error);
  // Send to error tracking
  sentry.captureException(error);
};
```

---

## Session Management

### How Sessions Work

The widget uses **anonymous sessions** with optional email capture:

1. **Anonymous Chat** - User starts chatting immediately without signup
2. **Session Token** - Generated on first message, stored in localStorage
3. **Email Capture** - After 2+ messages, prompt appears (dismissable)
4. **Session Persistence** - Chat history persists across page reloads

### Session Lifecycle

```
User visits page
    ↓
Widget loads
    ↓
User clicks bubble
    ↓
[First message] → Init session (POST /api/v1/personas/username/{username}/init-session)
    ↓
Session token stored (localStorage: session_{username})
    ↓
[Subsequent messages] → Use existing token
    ↓
[After 2+ messages] → Show email prompt (if not dismissed)
    ↓
[Email submitted] → Associate email with session (POST /api/v1/sessions/{token}/provide-email)
    ↓
Session persists across page reloads
```

### Session Storage

Sessions are stored in browser localStorage:

```javascript
// Session token
localStorage.getItem("session_johndoe"); // "eyJ0eXAiOiJKV1QiLCJh..."

// Chat history
localStorage.getItem("messages_johndoe"); // '[{"id":"1","content":"Hi",...}]'

// Email (if provided)
localStorage.getItem("email_johndoe"); // "user@example.com"

// Email prompt dismissed
localStorage.getItem("email_dismissed_johndoe"); // "true"
```

### Pre-filling User Info

You can skip the email prompt by providing user info upfront:

```javascript
window.MyClone({
  expertUsername: "johndoe",
  user: {
    email: "user@example.com",
    name: "John Doe",
  },
});
```

This will:

- Skip email capture prompt
- Associate messages with the provided email immediately
- Store email in localStorage

### Clearing Session

To reset the chat:

```javascript
// Clear all session data
localStorage.removeItem("session_johndoe");
localStorage.removeItem("messages_johndoe");
localStorage.removeItem("email_johndoe");
localStorage.removeItem("email_dismissed_johndoe");

// Reload widget
widget.destroy();
window.MyClone({ expertUsername: "johndoe" });
```

---

## Customization

### Brand Colors

```javascript
window.MyClone({
  expertUsername: "johndoe",
  primaryColor: "#FF6B6B", // Your brand color
});
```

### Custom Bubble Icon

```javascript
window.MyClone({
  expertUsername: "johndoe",
  bubbleIcon: "https://yourdomain.com/chat-icon.png",
});
```

### Custom CSS

Override widget styles with custom CSS:

```javascript
window.MyClone({
  expertUsername: "johndoe",
  customCss: `
    .embed-bubble {
      width: 70px;
      height: 70px;
      border-radius: 15px;
    }
    .embed-chat-container {
      border-radius: 20px;
    }
  `,
});
```

### Positioning

#### Bubble Position

Place the bubble button in any corner:

```javascript
// Bottom-right (default)
window.MyClone({ expertUsername: "johndoe", position: "bottom-right" });

// Bottom-left
window.MyClone({ expertUsername: "johndoe", position: "bottom-left" });

// Top-right
window.MyClone({ expertUsername: "johndoe", position: "top-right" });

// Top-left
window.MyClone({ expertUsername: "johndoe", position: "top-left" });
```

#### Modal Position (Chatbot-Style UI)

By default, when the user clicks the bubble button, the chat modal opens in the **center** of the screen. For a traditional chatbot UI (like Intercom or Drift), you can position the modal in a corner instead.

Use the `layout.modalPosition` parameter to open the modal in any corner:

```javascript
// Modal opens in bottom-right corner (chatbot-style)
window.MyClone({
  expertUsername: "johndoe",
  layout: {
    modalPosition: "bottom-right",
  },
});

// Modal opens in bottom-left corner
window.MyClone({
  expertUsername: "johndoe",
  layout: {
    modalPosition: "bottom-left",
  },
});

// Modal opens in top-right corner
window.MyClone({
  expertUsername: "johndoe",
  layout: {
    modalPosition: "top-right",
  },
});

// Modal opens in top-left corner
window.MyClone({
  expertUsername: "johndoe",
  layout: {
    modalPosition: "top-left",
  },
});

// Modal centered (default behavior)
window.MyClone({
  expertUsername: "johndoe",
  // Don't set modalPosition, or set it to undefined
});
```

#### Complete Example with Positioning

```javascript
window.MyClone({
  expertUsername: "johndoe",
  widgetToken: "wgt_xxxxx",

  // Bubble button position (where the button sits)
  layout: {
    position: "bottom-right", // Bubble button position
    offsetX: "20px", // Distance from right edge
    offsetY: "20px", // Distance from bottom edge
    modalPosition: "bottom-right", // Modal opens in bottom-right corner
  },

  // Additional customization
  theme: {
    primaryColor: "#6366f1",
  },
  enableVoice: true,
});
```

**Note**: `modalPosition` only affects bubble mode. In inline or fullpage modes, the modal is always visible and this parameter is ignored.

---

## Advanced Usage

### Multiple Widgets

Load multiple experts on the same page:

```javascript
// Expert 1 - Sales
const salesWidget = window.MyClone({
  expertUsername: "sales-expert",
  position: "bottom-right",
  bubbleText: "Talk to Sales",
  primaryColor: "#10B981",
});

// Expert 2 - Support
const supportWidget = window.MyClone({
  expertUsername: "support-expert",
  position: "bottom-left",
  bubbleText: "Get Support",
  primaryColor: "#3B82F6",
});
```

### Conditional Loading

Show widget based on conditions:

```javascript
// Only show to logged-in users
if (user.isLoggedIn) {
  window.MyClone({
    expertUsername: "johndoe",
    user: {
      email: user.email,
      name: user.name,
    },
  });
}

// Show different expert based on page
if (window.location.pathname.includes("/pricing")) {
  window.MyClone({ expertUsername: "sales-expert" });
} else {
  window.MyClone({ expertUsername: "support-expert" });
}
```

### Programmatic Control

Control widget programmatically:

```javascript
const widget = window.MyClone({ expertUsername: "johndoe" });

// Open widget when user clicks a button
document.getElementById("help-button").addEventListener("click", () => {
  widget.open();
});

// Close after 30 seconds
setTimeout(() => {
  widget.close();
}, 30000);

// Open widget for new users
if (isNewUser) {
  setTimeout(() => widget.open(), 5000); // Open after 5s
}
```

### Chatbot-Style Modal Positioning

Create a traditional chatbot UI with the modal in the bottom-right corner:

```javascript
window.MyClone({
  expertUsername: "johndoe",
  widgetToken: "wgt_xxxxx",

  // Position bubble and modal in bottom-right corner
  layout: {
    position: "bottom-right", // Bubble position
    modalPosition: "bottom-right", // Modal opens in corner (not centered)
    offsetX: "20px", // Distance from right edge
    offsetY: "20px", // Distance from bottom edge
  },

  // Custom theme
  theme: {
    primaryColor: "#3B82F6",
    backgroundColor: "#fff4eb",
  },

  // Features
  enableVoice: true,
  bubbleText: "Chat with us",

  // Track usage
  onOpen: () => analytics.track("Chatbot Opened"),
  onClose: () => analytics.track("Chatbot Closed"),
  onMessage: (msg) => analytics.track("Message Sent", { msg }),
});
```

**Result**: Traditional chatbot UI similar to Intercom, Drift, or Zendesk. The modal stays in the corner when expanded, unlike the centered modal (default behavior).

### A/B Testing

Test different configurations:

```javascript
// Variant A - Centered modal (default)
if (Math.random() < 0.5) {
  window.MyClone({
    expertUsername: "johndoe",
    enableVoice: true,
    onOpen: () => analytics.track("Widget Opened", { variant: "centered" }),
  });
}
// Variant B - Chatbot-style (bottom-right)
else {
  window.MyClone({
    expertUsername: "johndoe",
    layout: {
      modalPosition: "bottom-right",
    },
    enableVoice: true,
    onOpen: () => analytics.track("Widget Opened", { variant: "corner" }),
  });
}
```

---

## Development

### Local Development

1. Clone the repository:

```bash
git clone https://github.com/yourusername/myclone-frontend.git
cd myclone-frontend
```

2. Install dependencies:

```bash
pnpm install
```

3. Start dev servers:

```bash
# Terminal 1 - Next.js dev server
pnpm dev

# Terminal 2 - Watch mode for embed SDK (optional)
pnpm build:embed --watch
```

4. Test the widget:
   - Create `public/test-embed.html`
   - Load `http://localhost:3000/test-embed.html`

### Building for Production

```bash
# Build Next.js app
pnpm build

# Build embed SDK
pnpm build:embed
```

Output:

- `public/embed/myclone-embed.js` - SDK loader
- `public/embed/app.html` - Iframe template
- `public/embed/assets/` - CSS and JS bundles

### Project Structure

```
src/embed/
├── sdk/                 # Vanilla JS SDK (runs on host page)
│   ├── index.ts        # Main export
│   ├── loader.ts       # Widget loader class
│   ├── messaging.ts    # PostMessage communication
│   └── types.ts        # TypeScript interfaces
├── app/                 # React app (runs in iframe)
│   ├── EmbedApp.tsx    # Main widget component
│   ├── EmbedBubble.tsx # Bubble button
│   └── index.tsx       # Entry point
└── styles/
    └── embed.css       # Widget-specific styles

vite.embed.config.ts    # Vite build configuration
```

### Architecture

```
Host Page (example.com)
    ↓
Loads myclone-embed.js (Vanilla JS SDK)
    ↓
Creates <iframe src="/embed/app.html?v=timestamp">
    ↓
Iframe loads React app
    ↓
PostMessage communication established
    ↓
User interacts → Messages via PostMessage → API calls
```

### Caching Strategy

**Stable Asset Names** - No content hashes to prevent breaking on deploy:

- ✅ `app.html` - HTML template (cache-busted via query param)
- ✅ `app.js` - React bundle (stable filename, 872KB)
- ✅ `app.css` - Styles (stable filename, 90KB)
- ✅ `myclone-embed.js` - SDK loader (stable filename, 5KB)
- ⚠️ `messaging-*.js` - Dynamic chunk (has hash, but OK - see below)

**Cache Busting**:

- Iframe URL: `app.html?v=${Date.now()}` - Fresh load on every widget init
- Browser will cache assets (`app.js`, `app.css`) but reload iframe
- Deploy safely without breaking existing integrations

**Why no hashes?**

- Content hashes change on every build (e.g., `app-abc123.js`)
- External websites reference `app.html` which hardcodes asset names
- Changing hashes would break widgets after each deploy
- Solution: Stable filenames + query parameter cache-busting

**What about `messaging-J9wwfmRm.js`?**

- This is a **code-split chunk** for PostMessage module
- Dynamically imported by `app.js` at runtime
- Has a hash because `app.js` resolves it programmatically
- Safe to have hash - not directly referenced in HTML

**Source Maps (`.map` files)**:

- ❌ **Disabled in production** for security and size (saves 4MB+)
- 🐛 **Enable for debugging**: `pnpm build:embed:debug`
- Maps minified code back to readable source for DevTools

---

## Troubleshooting

### Widget Not Appearing

**Problem**: Script loads but widget doesn't show

**Solutions**:

- Check browser console for errors
- Verify `expertUsername` is correct
- Check if `window.MyClone` is defined
- Ensure no CSP blocking iframe

```javascript
// Debug mode
console.log(window.MyClone); // Should be a function
```

### Styles Not Working

**Problem**: Widget appears unstyled or broken

**Solutions**:

- Hard refresh (Ctrl+Shift+R) to clear cache
- Check if CSS file loads: `/embed/assets/app-*.css`
- Verify no CSS conflicts with host page
- Check browser console for 404 errors

### PostMessage Errors

**Problem**: `Failed to connect to widget` error

**Solutions**:

- Ensure iframe loads successfully
- Check if host page blocks iframes (X-Frame-Options)
- Verify `/embed/app.html` is accessible
- Check browser console for CSP violations

### Session Not Persisting

**Problem**: Chat history clears on page reload

**Solutions**:

- Check if localStorage is enabled
- Verify not in incognito/private mode
- Check if cookies are blocked
- Ensure same `expertUsername` is used

### CORS Issues

**Problem**: API requests fail with CORS error

**Solutions**:

- Verify API URL in environment variables
- Check backend CORS configuration
- Ensure credentials are included in fetch

### Build Errors

**Problem**: `pnpm build:embed` fails

**Solutions**:

```bash
# Clear cache and rebuild
rm -rf node_modules/.vite
rm -rf public/embed/assets/*
pnpm install
pnpm build:embed
```

### Common Errors

| Error                           | Cause                | Solution                              |
| ------------------------------- | -------------------- | ------------------------------------- |
| `expertUsername is required`    | Missing config       | Add `expertUsername` to config        |
| `Failed to load PostCSS config` | Missing dependencies | Run `pnpm install`                    |
| `Invalid environment variables` | Missing `.env`       | Copy `.env.example` to `.env.local`   |
| `404 on /embed/assets/*.js`     | Asset hash mismatch  | Update `app.html` with correct hashes |

---

## Support

- **Documentation**: https://github.com/yourusername/myclone-frontend/tree/main/docs
- **Issues**: https://github.com/yourusername/myclone-frontend/issues
- **Email**: support@yourdomain.com

---

## License

MIT License - See LICENSE file for details
