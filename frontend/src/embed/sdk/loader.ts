/**
 * MyClone Embed SDK Loader
 * Creates and manages the widget iframe with parent-child communication
 *
 * In bubble mode, the bubble is rendered instantly using vanilla JS/CSS
 * (via BubbleRenderer) and the iframe is deferred until the user clicks
 * the bubble or preloaded in the background after 3 seconds.
 */

import { BubbleRenderer } from "./bubble";
import { ParentMessenger } from "./messaging";
import type {
  MyCloneConfig,
  MyCloneWidget,
  ChildMethods,
  WidgetPosition,
  WidgetSizeConfig,
  WidgetThemeConfig,
  WidgetLayoutConfig,
  WidgetBrandingConfig,
} from "./types";

/**
 * Capture the script's origin at module load time
 * This is used to construct absolute URLs for cross-origin embeds
 */
let SCRIPT_ORIGIN = "";
if (typeof window !== "undefined" && document.currentScript) {
  const scriptElement = document.currentScript as HTMLScriptElement;
  try {
    const scriptUrl = new URL(scriptElement.src);
    SCRIPT_ORIGIN = scriptUrl.origin;
  } catch (e) {
    console.warn("MyClone: Failed to determine script origin", e);
  }
}

/**
 * Default size configuration
 */
const DEFAULT_SIZE: WidgetSizeConfig = {
  width: "900px",
  height: "820px",
  bubbleSize: "80px",
  borderRadius: "16px",
};

/**
 * Default theme configuration
 * Colors match the agent page theme (amber/peach)
 */
const DEFAULT_THEME: WidgetThemeConfig = {
  primaryColor: "#f59e0b", // amber-500 (ai-amber from globals.css)
  backgroundColor: "#fff4eb", // peach-light background
  textColor: "#111827", // gray-900
  textSecondaryColor: "#374151", // gray-700
  bubbleTextColor: "#ffffff",
  botMessageBg: "#ffffff", // white with border
};

/**
 * Default layout configuration
 */
const DEFAULT_LAYOUT: WidgetLayoutConfig = {
  position: "bottom-right",
  offsetX: "24px",
  offsetY: "24px",
  modalOffsetX: "0px",
  modalOffsetY: "10px",
  modalPosition: undefined,
};

/**
 * Default branding configuration
 */
const DEFAULT_BRANDING: WidgetBrandingConfig = {
  showBranding: true,
  showHeader: true,
  showAvatar: true,
};

/**
 * Default configuration values
 */
const DEFAULT_CONFIG: Partial<MyCloneConfig> = {
  mode: "bubble",
  position: "bottom-right",
  primaryColor: "#f59e0b", // amber-500 to match theme
  bubbleText: "Chat with me",
  enableVoice: false,
  inputPlaceholder: "Type your message...",
  zIndex: 999999,
  height: "820px",
  size: DEFAULT_SIZE,
  theme: DEFAULT_THEME,
  layout: DEFAULT_LAYOUT,
  branding: DEFAULT_BRANDING,
};

/**
 * Creates a MyClone widget instance
 */
export class MyCloneLoader implements MyCloneWidget {
  private config: Required<
    Omit<
      MyCloneConfig,
      | "personaName"
      | "bubbleIcon"
      | "welcomeMessage"
      | "customCss"
      | "user"
      | "onOpen"
      | "onClose"
      | "onMessage"
      | "onEmailSubmit"
      | "onError"
    >
  > &
    Pick<
      MyCloneConfig,
      "personaName" | "bubbleIcon" | "welcomeMessage" | "customCss" | "user"
    >;
  private container: HTMLDivElement | null = null;
  private iframe: HTMLIFrameElement | null = null;
  private messenger: ParentMessenger<ChildMethods> | null = null;
  private callbacks: Pick<
    MyCloneConfig,
    "onOpen" | "onClose" | "onMessage" | "onEmailSubmit" | "onError"
  >;

  // Instant bubble state
  private bubbleRenderer: BubbleRenderer | null = null;
  private _expanded: boolean = false;
  private iframeLoadPromise: Promise<void> | null = null;
  private preloadTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(config: MyCloneConfig) {
    // Validate required config
    if (!config.expertUsername) {
      throw new Error("MyClone: expertUsername is required");
    }

    // Validate inline mode requirements
    if (config.mode === "inline" && !config.container) {
      throw new Error(
        'MyClone: container is required when mode is "inline". Provide a CSS selector like "#chat-container"',
      );
    }

    // Fullpage mode doesn't need container - it takes over the whole page
    if (config.mode === "fullpage" && config.container) {
      console.warn(
        'MyClone: container is ignored when mode is "fullpage". The widget will take over the entire page.',
      );
    }

    // Merge nested configs with defaults
    const mergedSize = { ...DEFAULT_SIZE, ...config.size };
    const mergedTheme = { ...DEFAULT_THEME, ...config.theme };
    const mergedLayout = { ...DEFAULT_LAYOUT, ...config.layout };
    const mergedBranding = { ...DEFAULT_BRANDING, ...config.branding };

    // Handle legacy config options - map to new structure
    // Legacy primaryColor -> theme.primaryColor
    if (config.primaryColor && !config.theme?.primaryColor) {
      mergedTheme.primaryColor = config.primaryColor;
    }
    // Legacy position -> layout.position
    if (config.position && !config.layout?.position) {
      mergedLayout.position = config.position;
    }
    // Legacy height -> size.height
    if (config.height && !config.size?.height) {
      mergedSize.height = config.height;
    }

    // Merge with defaults
    this.config = {
      ...DEFAULT_CONFIG,
      ...config,
      size: mergedSize,
      theme: mergedTheme,
      layout: mergedLayout,
      branding: mergedBranding,
      // Ensure legacy fields are synced with new structure
      primaryColor: mergedTheme.primaryColor,
      position: mergedLayout.position,
      height: mergedSize.height,
    } as typeof this.config;

    // Store callbacks separately
    this.callbacks = {
      onOpen: config.onOpen,
      onClose: config.onClose,
      onMessage: config.onMessage,
      onEmailSubmit: config.onEmailSubmit,
      onError: config.onError,
    };

    // Initialize the widget
    this.init();
  }

  /**
   * Initialize the widget by creating container and iframe.
   * In bubble mode, renders the bubble instantly and defers iframe loading.
   */
  private init(): void {
    try {
      // Ensure DOM is ready before creating container
      this.ensureDOMReady(() => {
        this.createContainer();

        if (this.isBubbleMode()) {
          // Bubble mode: render the bubble instantly, defer iframe
          this.createBubble();
          this.scheduleIframePreload();
        } else {
          // Inline/fullpage: create iframe immediately (no bubble needed)
          this.createIframe();
          this.waitForIframeLoad();
        }
      });
    } catch (error) {
      this.handleError(error as Error);
    }
  }

  /**
   * Check if the widget is in a mode that shows a bubble
   */
  private isBubbleMode(): boolean {
    return this.config.mode === "bubble";
  }

  /**
   * Create the vanilla JS/CSS bubble in the container
   */
  private createBubble(): void {
    if (!this.container) return;

    const bgColor =
      this.config.theme?.bubbleBackgroundColor ||
      this.config.theme?.primaryColor ||
      this.config.primaryColor;

    this.bubbleRenderer = new BubbleRenderer(this.container, {
      bubbleSize: this.config.size?.bubbleSize || "80px",
      bgColor,
      bubbleTextColor: this.config.theme?.bubbleTextColor || "#ffffff",
      primaryColor: this.config.primaryColor,
      bubbleText: this.config.bubbleText,
      bubbleIcon:
        this.config.bubbleIcon ||
        this.config.branding?.bubbleIcon ||
        this.config.branding?.avatarUrl,
      simpleBubble: this.config.branding?.simpleBubble === true,
      tooltipMessages: [
        "Talk to me!",
        "Ask me anything",
        "Need help?",
        "Let's chat!",
      ],
      position: this.config.position,
    });

    this.bubbleRenderer.render();
    this.bubbleRenderer.onClick(() => this.handleBubbleClick());
  }

  /**
   * Handle bubble click: toggle expanded state and manage iframe lifecycle
   */
  private async handleBubbleClick(): Promise<void> {
    if (!this.bubbleRenderer) return;

    if (this._expanded) {
      // CLOSING — hide iframe, show bubble
      this._expanded = false;
      this.bubbleRenderer.setExpanded(false);
      this.shrinkContainer();
      this.callbacks.onClose?.();
    } else {
      // OPENING — show iframe, swap to close icon
      this._expanded = true;
      this.bubbleRenderer.setExpanded(true);
      this.callbacks.onOpen?.();

      if (!this.iframe) {
        // First click before preload: create iframe now
        this.createIframe();
      }

      // Tell the iframe to expand its internal state
      // (needed after the iframe's own close button set isExpanded=false)
      if (this.messenger) {
        this.messenger.call("open").catch(() => {});
      }

      this.expandContainer();
    }
  }

  /**
   * Schedule iframe preload after a delay so it's ready when user clicks.
   * The iframe is created hidden in the background.
   */
  private scheduleIframePreload(): void {
    this.preloadTimer = setTimeout(() => {
      if (!this.iframe && this.container) {
        this.createIframe();
        this.hideIframe();
        // Silently handle preload errors — will retry on click if needed
        this.iframeLoadPromise?.catch(() => {});
      }
    }, 3000);
  }

  /**
   * Ensure the iframe is loaded and the messenger connection is established.
   * Returns immediately if already connected, otherwise waits for the load promise
   * created in createIframe().
   */
  private ensureIframeReady(): Promise<void> {
    if (this.messenger) return Promise.resolve();
    if (this.iframeLoadPromise) return this.iframeLoadPromise;
    return Promise.reject(new Error("No iframe"));
  }

  /**
   * Hide the iframe (used during preload)
   */
  private hideIframe(): void {
    if (!this.iframe) return;
    this.iframe.style.visibility = "hidden";
    this.iframe.style.position = "absolute";
    this.iframe.style.width = "0";
    this.iframe.style.height = "0";
    this.iframe.style.pointerEvents = "none";
  }

  /**
   * Show the iframe (when opening the chat)
   */
  private showIframe(): void {
    if (!this.iframe) return;
    this.iframe.style.visibility = "visible";
    this.iframe.style.position = "";
    this.iframe.style.width = "100%";
    this.iframe.style.height = "100%";
    this.iframe.style.pointerEvents = "auto";
  }

  /**
   * Ensure DOM is ready before executing callback
   * This allows the widget to work when script is placed in <head>
   */
  private ensureDOMReady(callback: () => void): void {
    if (document.body) {
      // DOM is already ready
      callback();
    } else if (document.readyState === "loading") {
      // DOM is still loading, wait for DOMContentLoaded
      document.addEventListener("DOMContentLoaded", callback, { once: true });
    } else {
      // DOM is ready but body doesn't exist yet (edge case)
      // Try again on next tick
      setTimeout(callback, 0);
    }
  }

  /**
   * Wait for iframe to load before setting up connection
   * Used only for inline/fullpage modes (non-bubble modes)
   */
  private waitForIframeLoad(): void {
    if (!this.iframe) {
      throw new Error("Iframe not created");
    }

    this.iframe.addEventListener("load", () => {
      this.setupConnection().catch((error) => {
        this.handleError(error as Error);
      });
    });

    this.iframe.addEventListener("error", (error) => {
      console.error("❌ Iframe failed to load:", error);
      this.handleError(new Error("Failed to load iframe"));
    });
  }

  /**
   * Create the container element
   */
  private createContainer(): void {
    const { mode } = this.config;

    if (mode === "inline") {
      // Inline mode: Use existing container from DOM
      const containerElement = document.querySelector(
        this.config.container!,
      ) as HTMLDivElement;

      if (!containerElement) {
        throw new Error(
          `MyClone: Container "${this.config.container}" not found in DOM`,
        );
      }

      this.container = containerElement;
      this.container.style.cssText = this.getInlineContainerStyles();
    } else if (mode === "fullpage") {
      // Fullpage mode: Take over the entire page
      this.container = document.createElement("div");
      this.container.id = "myclone-widget-container";
      this.container.style.cssText = this.getFullpageContainerStyles();
      document.body.appendChild(this.container);

      // Hide scrollbar on body for fullpage mode
      document.body.style.overflow = "hidden";
      document.documentElement.style.overflow = "hidden";
    } else {
      // Bubble mode: Create floating container
      this.container = document.createElement("div");
      this.container.id = "myclone-widget-container";
      this.container.style.cssText = this.getContainerStyles();
      document.body.appendChild(this.container);
    }
  }

  /**
   * Get CSS styles for the container based on position
   * In bubble mode, we constrain the container to the bubble size to prevent
   * blocking page clicks. The container expands to full viewport when modal opens.
   */
  private getContainerStyles(): string {
    const { position, zIndex } = this.config;
    const bubbleSize = this.config.size?.bubbleSize || "80px";
    const bubbleSizeNum = parseInt(bubbleSize) || 80;

    // Size the container to fit the bubble only. Ripple waves and tooltip
    // overflow visually via overflow:visible. This avoids negative offsets
    // that push the container off-screen on sites with overflow:hidden.
    const baseStyles = `
      position: fixed;
      z-index: ${zIndex};
      width: ${bubbleSizeNum}px;
      height: ${bubbleSizeNum}px;
      overflow: visible;
    `;

    const positionStyles = this.getPositionStyles(position);

    return baseStyles + positionStyles;
  }

  /**
   * Get position-specific CSS styles
   * @param position - Widget position
   */
  private getPositionStyles(position: WidgetPosition): string {
    const offsetX = this.config.layout?.offsetX || "20px";
    const offsetY = this.config.layout?.offsetY || "20px";

    switch (position) {
      case "bottom-right":
        return `bottom: ${offsetY}; right: ${offsetX};`;
      case "bottom-left":
        return `bottom: ${offsetY}; left: ${offsetX};`;
      case "top-right":
        return `top: ${offsetY}; right: ${offsetX};`;
      case "top-left":
        return `top: ${offsetY}; left: ${offsetX};`;
      default:
        return `bottom: ${offsetY}; right: ${offsetX};`;
    }
  }

  /**
   * Get CSS styles for inline mode container
   */
  private getInlineContainerStyles(): string {
    const { height } = this.config;
    return `
      position: relative;
      width: 100%;
      height: ${height};
      display: block;
    `;
  }

  /**
   * Get CSS styles for fullpage mode container
   */
  private getFullpageContainerStyles(): string {
    const { zIndex } = this.config;
    return `
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      width: 100vw;
      height: 100vh;
      z-index: ${zIndex};
      background: white;
    `;
  }

  /**
   * Expand container to full viewport when modal opens
   */
  private expandContainer(): void {
    if (!this.container) return;

    // Skip for inline and fullpage modes (always expanded)
    if (this.config.mode === "inline" || this.config.mode === "fullpage")
      return;

    this.container.style.cssText = `
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      width: 100vw;
      height: 100vh;
      z-index: ${this.config.zIndex};
      pointer-events: none;
    `;

    // Make iframe visible and allow pointer events
    this.showIframe();
  }

  /**
   * Shrink container back to corner position when modal closes
   */
  private shrinkContainer(): void {
    if (!this.container) return;

    // Skip for inline and fullpage modes (always expanded)
    if (this.config.mode === "inline" || this.config.mode === "fullpage")
      return;

    // Disable transition so the container snaps back instantly
    // (prevents the bubble from visibly jumping up then settling)
    const styles = this.getContainerStyles();
    this.container.style.cssText = styles.replace(
      "transition: all 0.3s ease-in-out;",
      "transition: none;",
    );

    // Hide iframe when collapsed
    this.hideIframe();
  }

  /**
   * Create the iframe element and set up the load promise.
   * The iframe starts loading immediately once appended to DOM.
   */
  private createIframe(): void {
    if (!this.container) {
      throw new Error("Container not created");
    }

    this.iframe = document.createElement("iframe");
    this.iframe.id = "myclone-widget-iframe";
    this.iframe.style.cssText = this.getIframeStyles();

    // Security: sandbox restricts the iframe so it can't navigate the parent page,
    // access parent cookies, etc. Only grant the minimum permissions needed.
    this.iframe.setAttribute(
      "sandbox",
      "allow-scripts allow-same-origin allow-forms allow-popups allow-popups-to-escape-sandbox",
    );

    // Full permissions policy for microphone access (required for voice chat)
    this.iframe.setAttribute(
      "allow",
      "microphone; camera; autoplay; display-capture",
    );
    this.iframe.setAttribute("title", "MyClone Chat Widget");

    // Set up the load promise BEFORE setting src (to guarantee we catch the load event)
    this.iframeLoadPromise = new Promise<void>((resolve, reject) => {
      this.iframe!.addEventListener(
        "load",
        () => {
          this.setupConnection().then(resolve).catch(reject);
        },
        { once: true },
      );
      this.iframe!.addEventListener(
        "error",
        () => reject(new Error("Failed to load iframe")),
        { once: true },
      );
    });

    // Set src and append — this starts the actual loading
    this.iframe.src = this.buildIframeUrl();
    this.container.appendChild(this.iframe);
  }

  /**
   * Build the iframe URL with config as query params
   */
  private buildIframeUrl(): string {
    // In production, this would be your deployed URL
    // For now, we'll use relative path (will be updated in deployment phase)
    const baseUrl = this.getBaseUrl();

    const params = new URLSearchParams({
      expertUsername: this.config.expertUsername,
      widgetToken: this.config.widgetToken,
      mode: this.config.mode,
      position: this.config.position,
      primaryColor: this.config.primaryColor,
      bubbleText: this.config.bubbleText,
      enableVoice: String(this.config.enableVoice),
      inputPlaceholder: this.config.inputPlaceholder,
      height: this.config.height,
    });

    if (this.config.personaName) {
      params.set("personaName", this.config.personaName);
    }

    if (this.config.bubbleIcon) {
      params.set("bubbleIcon", this.config.bubbleIcon);
    }

    if (this.config.welcomeMessage) {
      params.set("welcomeMessage", this.config.welcomeMessage);
    }

    if (this.config.customCss) {
      params.set("customCss", this.config.customCss);
    }

    if (this.config.user) {
      params.set("user", JSON.stringify(this.config.user));
    }

    // ============================================
    // NEW CUSTOMIZATION PARAMETERS
    // ============================================

    // Size & Dimensions
    if (this.config.size) {
      params.set("size", JSON.stringify(this.config.size));
    }

    // Theme & Colors
    if (this.config.theme) {
      params.set("theme", JSON.stringify(this.config.theme));
    }

    // Layout & Positioning
    if (this.config.layout) {
      params.set("layout", JSON.stringify(this.config.layout));
    }

    // Branding
    if (this.config.branding) {
      params.set("branding", JSON.stringify(this.config.branding));
    }

    // Tell iframe that the loader handles the bubble
    if (this.bubbleRenderer) {
      params.set("loaderBubble", "true");
    }

    // Pass environment variables needed by the iframe
    // These are required for API calls and LiveKit connection
    if (typeof window !== "undefined") {
      // Try to get from window (user can override)
      // Otherwise use build-time injected env values
      const apiUrl =
        (window as { CONVOXAI_API_URL?: string }).CONVOXAI_API_URL ||
        process.env.NEXT_PUBLIC_API_URL ||
        SCRIPT_ORIGIN ||
        window.location.origin;

      const livekitUrl =
        (window as { CONVOXAI_LIVEKIT_URL?: string }).CONVOXAI_LIVEKIT_URL ||
        process.env.NEXT_PUBLIC_LIVEKIT_URL ||
        "";

      params.set("apiUrl", apiUrl);
      if (livekitUrl) {
        params.set("livekitUrl", livekitUrl);
      }
    }

    // Use & instead of ? since baseUrl already has ?v=timestamp
    const separator = baseUrl.includes("?") ? "&" : "?";
    return `${baseUrl}${separator}${params.toString()}`;
  }

  /**
   * Get base URL for iframe (different for dev/prod)
   */
  private getBaseUrl(): string {
    // Use the script origin captured at module load time
    // This allows the embed to work across different domains
    if (SCRIPT_ORIGIN) {
      return `${SCRIPT_ORIGIN}/embed/app.html?v=${Date.now()}`;
    }

    // Fallback to relative path (for same-origin embeds)
    return `/embed/app.html?v=${Date.now()}`;
  }

  /**
   * Get CSS styles for the iframe
   */
  private getIframeStyles(): string {
    return `
      width: 100%;
      height: 100%;
      border: none;
      background: transparent;
      color-scheme: light;
      pointer-events: auto;
    `;
  }

  /**
   * Setup postMessage connection with child iframe
   */
  private async setupConnection(): Promise<void> {
    if (!this.iframe) {
      throw new Error("Iframe not created");
    }

    // Define methods the parent exposes to the child
    const parentMethods = {
      notifyOpen: () => {
        // In bubble mode, the loader handles expand/open
        if (!this.bubbleRenderer) {
          this.expandContainer();
        }
        this.callbacks.onOpen?.();
      },
      notifyClose: () => {
        // Update the loader bubble when iframe requests close
        if (this.bubbleRenderer) {
          this._expanded = false;
          this.bubbleRenderer.setExpanded(false);
        }
        this.shrinkContainer();
        this.callbacks.onClose?.();
      },
      notifyMessage: (...args: unknown[]) => {
        const message = args[0] as string;
        this.callbacks.onMessage?.(message);
      },
      notifyEmailSubmit: (...args: unknown[]) => {
        const email = args[0] as string;
        this.callbacks.onEmailSubmit?.(email);
      },
      notifyError: (...args: unknown[]) => {
        const error = args[0] as string;
        this.callbacks.onError?.(new Error(error));
      },
      notifyAvatarUrl: (...args: unknown[]) => {
        const url = args[0] as string;
        if (url && this.bubbleRenderer) {
          this.bubbleRenderer.updateIcon(url);
        }
      },
    };

    // Create messenger
    this.messenger = new ParentMessenger<ChildMethods>(
      this.iframe,
      parentMethods,
    );

    try {
      // Wait for child to be ready
      await this.messenger.waitForReady();
    } catch (error) {
      console.error("❌ Connection failed:", error);
      this.handleError(
        new Error(`Failed to connect to widget: ${(error as Error).message}`),
      );
    }
  }

  /**
   * Public API: Open the widget
   */
  async open(): Promise<void> {
    if (this.bubbleRenderer && !this._expanded) {
      await this.handleBubbleClick();
      return;
    }

    if (this.messenger) {
      await this.messenger.call("open");
    }
  }

  /**
   * Public API: Close the widget
   */
  async close(): Promise<void> {
    if (this.bubbleRenderer && this._expanded) {
      await this.handleBubbleClick();
      return;
    }

    if (this.messenger) {
      await this.messenger.call("close");
    }
  }

  /**
   * Public API: Toggle the widget
   */
  async toggle(): Promise<void> {
    if (this.bubbleRenderer) {
      await this.handleBubbleClick();
      return;
    }

    if (this.messenger) {
      await this.messenger.call("toggle");
    }
  }

  /**
   * Public API: Set user information
   */
  async setUser(user: MyCloneConfig["user"]): Promise<void> {
    this.config.user = user;

    if (this.messenger) {
      await this.messenger.call("setUser", user);
    }
    // If messenger isn't ready yet, user config is already stored
    // and will be passed via URL params when iframe is created
  }

  /**
   * Public API: Check if widget is expanded
   */
  async isExpanded(): Promise<boolean> {
    if (this.bubbleRenderer) {
      return this._expanded;
    }

    if (this.messenger) {
      return (await this.messenger.call("isExpanded")) as boolean;
    }

    return false;
  }

  /**
   * Public API: Destroy the widget
   */
  destroy(): void {
    // Cancel preload timer
    if (this.preloadTimer !== null) {
      clearTimeout(this.preloadTimer);
      this.preloadTimer = null;
    }

    // Destroy bubble renderer
    if (this.bubbleRenderer) {
      this.bubbleRenderer.destroy();
      this.bubbleRenderer = null;
    }

    // Destroy messenger connection
    if (this.messenger) {
      this.messenger.destroy();
      this.messenger = null;
    }

    // Restore body overflow if fullpage mode
    if (this.config.mode === "fullpage") {
      document.body.style.overflow = "";
      document.documentElement.style.overflow = "";
    }

    // Remove container from DOM
    if (this.container && this.container.parentNode) {
      this.container.parentNode.removeChild(this.container);
    }

    // Clean up references
    this.container = null;
    this.iframe = null;
    this.iframeLoadPromise = null;
  }

  /**
   * Handle errors
   */
  private handleError(error: Error): void {
    console.error("MyClone Widget Error:", error);
    this.callbacks.onError?.(error);
  }
}
