/**
 * MyClone Embed SDK - Bubble Renderer
 *
 * Vanilla JS/CSS replica of the React EmbedBubble component.
 * Renders the chat bubble instantly on the host page without React or
 * framer-motion dependencies. Designed to run on customer websites.
 *
 * No external dependencies. All DOM creation via document.createElement.
 * Global scope is not polluted. Everything is cleaned up in destroy().
 */

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface BubbleConfig {
  /** e.g. "80px" */
  bubbleSize: string;
  /** hex color for bubble background */
  bgColor: string;
  /** hex color for icon, default "#ffffff" */
  bubbleTextColor: string;
  /** hex color (used only for future extensibility; bgColor is the primary) */
  primaryColor: string;
  /** aria-label text */
  bubbleText: string;
  /** avatar image URL – shown when the persona has loaded */
  bubbleIcon?: string;
  /** when true: no waves, no float, no tooltip */
  simpleBubble: boolean;
  /** cycling tooltip texts (at least one entry expected) */
  tooltipMessages: string[];
  /** widget position for keeping bubble in corner when expanded */
  position: string;
}

// ---------------------------------------------------------------------------
// Utility: adjust color opacity
// ---------------------------------------------------------------------------

function adjustColorOpacity(color: string, opacity: number): string {
  if (color.startsWith("rgba")) {
    return color.replace(/[\d.]+\)$/, `${opacity})`);
  }
  if (color.startsWith("#")) {
    const hex = color.slice(1);
    const r = parseInt(hex.slice(0, 2), 16);
    const g = parseInt(hex.slice(2, 4), 16);
    const b = parseInt(hex.slice(4, 6), 16);
    return `rgba(${r}, ${g}, ${b}, ${opacity})`;
  }
  return color;
}

// ---------------------------------------------------------------------------
// SVG icon helpers
// ---------------------------------------------------------------------------

function createSvg(
  viewBox: string,
  width: number,
  height: number,
  innerHTML: string,
): SVGSVGElement {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", viewBox);
  svg.setAttribute("width", String(width));
  svg.setAttribute("height", String(height));
  svg.setAttribute("fill", "none");
  svg.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  // innerHTML is safe here – all values are internal SVG path strings
  svg.innerHTML = innerHTML;
  return svg;
}

function createMessageIcon(color: string, size: number): SVGSVGElement {
  return createSvg(
    "0 0 28 28",
    size,
    size,
    `<path d="M14 2.33337C7.55672 2.33337 2.33337 7.03171 2.33337 12.8334C2.33337 15.3184 3.29837 17.5867 4.90171 19.3634V25.6667L10.7617 22.5167C11.8017 22.7517 12.8834 22.8767 14 22.8767C20.4434 22.8767 25.6667 18.1784 25.6667 12.3767C25.6667 6.57504 20.4434 2.33337 14 2.33337Z" fill="${color}" />`,
  );
}

function createCloseIcon(color: string, size: number): SVGSVGElement {
  return createSvg(
    "0 0 24 24",
    size,
    size,
    `<path d="M18 6L6 18M6 6L18 18" stroke="${color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" />`,
  );
}

function createSparklesIcon(color: string, size: number): SVGSVGElement {
  return createSvg(
    "0 0 24 24",
    size,
    size,
    `<path d="M12 3L13.4 8.6L19 10L13.4 11.4L12 17L10.6 11.4L5 10L10.6 8.6L12 3Z" fill="${color}" />
     <path d="M19 15L19.8 17.2L22 18L19.8 18.8L19 21L18.2 18.8L16 18L18.2 17.2L19 15Z" fill="${color}" />
     <path d="M5 2L5.6 3.8L7.5 4.5L5.6 5.2L5 7L4.4 5.2L2.5 4.5L4.4 3.8L5 2Z" fill="${color}" />`,
  );
}

// ---------------------------------------------------------------------------
// CSS injection (singleton – injected once per page load)
// ---------------------------------------------------------------------------

const STYLE_ID = "myclone-bubble-styles";

function injectStyles(): void {
  if (document.getElementById(STYLE_ID)) return;

  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = `
    @keyframes myclone-pulse {
      0%   { transform: scale(1);   opacity: 0.4; }
      100% { transform: scale(1.7); opacity: 0;   }
    }

    @keyframes myclone-float {
      0%   { transform: translateY(0px);  }
      50%  { transform: translateY(-5px); }
      100% { transform: translateY(0px);  }
    }

    @keyframes myclone-tooltip-enter {
      from { opacity: 0; transform: translateX(10px) scale(0.9); }
      to   { opacity: 1; transform: translateX(0px)  scale(1);   }
    }

    @keyframes myclone-tooltip-exit {
      from { opacity: 1; transform: translateX(0px)  scale(1);   }
      to   { opacity: 0; transform: translateX(10px) scale(0.9); }
    }

    @keyframes myclone-icon-enter {
      from { opacity: 0; transform: scale(0); }
      to   { opacity: 1; transform: scale(1); }
    }

    .myclone-outer {
      position: relative;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .myclone-outer--collapsed {
      width: 100%;
      height: 100%;
    }

    .myclone-outer--expanded {
      position: fixed;
      z-index: 999999;
      pointer-events: auto;
    }

    .myclone-outer--expanded.myclone-pos-bottom-right {
      bottom: 24px;
      right: 24px;
    }
    .myclone-outer--expanded.myclone-pos-bottom-left {
      bottom: 24px;
      left: 24px;
    }
    .myclone-outer--expanded.myclone-pos-top-right {
      top: 24px;
      right: 24px;
    }
    .myclone-outer--expanded.myclone-pos-top-left {
      top: 24px;
      left: 24px;
    }

    .myclone-bubble-wrapper {
      position: relative;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .myclone-wave {
      position: absolute;
      border-radius: 9999px !important;
      opacity: 0;
      pointer-events: none;
      animation: myclone-pulse 2s cubic-bezier(0.4, 0, 0.2, 1) infinite;
    }

    .myclone-btn {
      position: relative;
      display: flex !important;
      align-items: center !important;
      justify-content: center !important;
      border-radius: 9999px !important;
      border: none !important;
      cursor: pointer !important;
      outline: none !important;
      pointer-events: auto;
      transition: transform 0.15s ease;
      padding: 0 !important;
      margin: 0 !important;
      box-sizing: border-box !important;
      overflow: hidden !important;
      /* Prevent host page CSS from overriding bubble styles */
    }

    .myclone-btn:hover  { transform: scale(1.1);  }
    .myclone-btn:active { transform: scale(0.95); }

    .myclone-btn--simple:hover { transform: scale(1.05); }

    .myclone-btn-float {
      animation: myclone-float 2s ease-in-out infinite;
    }

    .myclone-icon-wrap {
      display: flex;
      align-items: center;
      justify-content: center;
      animation: myclone-icon-enter 0.2s cubic-bezier(0.4, 0, 0.2, 1) both;
    }

    .myclone-icon-wrap--avatar {
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
    }

    .myclone-avatar {
      width: 100% !important;
      height: 100% !important;
      border-radius: 50% !important;
      object-fit: cover !important;
      border: 3px solid rgba(255, 255, 255, 0.9) !important;
      image-rendering: auto;
      filter: blur(0.3px);
      transform: scale(1.02);
    }

    .myclone-tooltip {
      position: absolute;
      top: 0;
      bottom: 0;
      right: 100%;
      margin-right: 12px;
      display: flex;
      align-items: center;
      pointer-events: none;
    }

    .myclone-tooltip--enter {
      animation: myclone-tooltip-enter 0.25s ease both;
    }

    .myclone-tooltip--exit {
      animation: myclone-tooltip-exit 0.2s ease both;
    }

    .myclone-tooltip__inner {
      position: relative;
      white-space: nowrap;
      border-radius: 12px;
      padding: 10px 16px;
      background-color: #1f2937;
      color: #ffffff;
      box-shadow: 0 4px 12px rgba(0,0,0,0.15);
      font-size: 14px;
      font-weight: 500;
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .myclone-tooltip__arrow {
      position: absolute;
      right: -8px;
      top: 50%;
      transform: translateY(-50%);
      width: 0;
      height: 0;
      border-top: 8px solid transparent;
      border-bottom: 8px solid transparent;
      border-left: 8px solid #1f2937;
    }
  `;

  document.head.appendChild(style);
}

// ---------------------------------------------------------------------------
// BubbleRenderer
// ---------------------------------------------------------------------------

export class BubbleRenderer {
  public isExpanded: boolean = false;

  // Config (immutable after construction)
  private readonly cfg: BubbleConfig;
  private readonly sizeNum: number;
  private readonly iconSize: number;
  /** CSS clamp() value for responsive bubble sizing */
  private readonly responsiveSize: string;

  // Root container supplied by caller
  private readonly container: HTMLDivElement;

  // DOM refs
  private outerEl: HTMLDivElement | null = null;
  private wrapperEl: HTMLDivElement | null = null;
  private floatEl: HTMLDivElement | null = null;
  private btnEl: HTMLButtonElement | null = null;
  private wave0: HTMLDivElement | null = null;
  private wave1: HTMLDivElement | null = null;
  private wave2: HTMLDivElement | null = null;
  private iconSlot: HTMLDivElement | null = null;
  private tooltipEl: HTMLDivElement | null = null;

  // State
  private tooltipIndex: number = 0;
  private tooltipVisible: boolean = false;
  private hasInteracted: boolean = false;
  private imageError: boolean = false;
  private currentIconUrl: string | undefined;

  // Timers
  private initialTooltipTimer: ReturnType<typeof setTimeout> | null = null;
  private hideTooltipTimer: ReturnType<typeof setTimeout> | null = null;
  private showAgainTimer: ReturnType<typeof setTimeout> | null = null;

  // Click callback
  private clickCallback: (() => void) | null = null;

  // Bound event listeners (stored so they can be removed on destroy)
  private boundHandleClick: () => void;

  constructor(container: HTMLDivElement, config: BubbleConfig) {
    this.container = container;
    this.cfg = config;
    this.sizeNum = parseInt(config.bubbleSize) || 80;
    this.iconSize = Math.round(this.sizeNum * 0.4);
    this.currentIconUrl = config.bubbleIcon;

    // Responsive size: scales down to 70% on small screens
    const minSize = Math.round(this.sizeNum * 0.7);
    this.responsiveSize = `clamp(${minSize}px, 10vw, ${this.sizeNum}px)`;

    this.boundHandleClick = this.handleClick.bind(this);
  }

  // ---------------------------------------------------------------------------
  // Public API
  // ---------------------------------------------------------------------------

  /**
   * Creates all DOM elements and injects styles into the page.
   * Must be called once after construction.
   */
  render(): void {
    injectStyles();
    this.preloadIcon();
    this.buildDOM();
    this.startTooltipCycle();
  }

  /**
   * Prefetch the bubble icon image so it's in the browser cache
   * by the time the DOM renders the <img> tag.
   */
  private preloadIcon(): void {
    if (this.currentIconUrl) {
      const img = new Image();
      img.src = this.currentIconUrl;
    }
  }

  /**
   * Toggle between open (X) and closed (message/avatar) icon.
   */
  setExpanded(expanded: boolean): void {
    this.isExpanded = expanded;

    // Update outer container class
    const posClass = `myclone-pos-${this.cfg.position || "bottom-right"}`;
    if (this.outerEl) {
      if (expanded) {
        this.outerEl.classList.remove("myclone-outer--collapsed");
        this.outerEl.classList.add("myclone-outer--expanded", posClass);
        this.outerEl.style.width = this.responsiveSize;
        this.outerEl.style.height = this.responsiveSize;
      } else {
        this.outerEl.classList.remove("myclone-outer--expanded", posClass);
        this.outerEl.classList.add("myclone-outer--collapsed");
        this.outerEl.style.width = "";
        this.outerEl.style.height = "";
      }
    }

    // Show/hide waves and float animation
    this.updateWavesVisibility();
    this.updateFloatAnimation();

    // Swap icon
    this.renderIcon();

    // Hide tooltip when expanded
    if (expanded && this.tooltipVisible) {
      this.hideTooltip(false);
    }

    // Restart cycle when collapsed (if user hasn't interacted yet)
    if (!expanded && !this.hasInteracted) {
      this.startTooltipCycle();
    }
  }

  /**
   * Update the avatar displayed inside the button.
   * Called after the persona loads and provides an icon URL.
   */
  updateIcon(iconUrl: string): void {
    this.currentIconUrl = iconUrl;
    this.imageError = false;
    if (!this.isExpanded) {
      this.renderIcon();
    }
  }

  /**
   * Register the click handler that will be invoked when the bubble is clicked.
   */
  onClick(callback: () => void): void {
    this.clickCallback = callback;
  }

  /**
   * Remove all DOM elements, timers, and event listeners created by this instance.
   */
  destroy(): void {
    // Clear timers
    this.clearAllTimers();
    if (this.floatResumeTimer) {
      clearTimeout(this.floatResumeTimer);
      this.floatResumeTimer = null;
    }

    // Remove event listeners
    if (this.btnEl) {
      this.btnEl.removeEventListener("click", this.boundHandleClick);
    }

    // Remove root element from container
    if (this.outerEl && this.container.contains(this.outerEl)) {
      this.container.removeChild(this.outerEl);
    }

    // Null refs
    this.outerEl = null;
    this.wrapperEl = null;
    this.floatEl = null;
    this.btnEl = null;
    this.wave0 = null;
    this.wave1 = null;
    this.wave2 = null;
    this.iconSlot = null;
    this.tooltipEl = null;
    this.clickCallback = null;
  }

  // ---------------------------------------------------------------------------
  // DOM construction
  // ---------------------------------------------------------------------------

  private buildDOM(): void {
    const { cfg } = this;

    // ── Outer container ────────────────────────────────────────────────────
    const outer = document.createElement("div");
    outer.className = "myclone-outer myclone-outer--collapsed";
    this.outerEl = outer;

    // ── Bubble wrapper (holds waves + float div + button) ──────────────────
    const wrapper = document.createElement("div");
    wrapper.className = "myclone-bubble-wrapper";
    this.wrapperEl = wrapper;

    // ── Waves ──────────────────────────────────────────────────────────────
    const waveDelays: [string, string, string] = ["0s", "0.65s", "1.3s"];
    const waves = waveDelays.map((delay) => {
      const wave = document.createElement("div");
      wave.className = "myclone-wave";
      wave.style.cssText = `
        width: ${this.responsiveSize};
        height: ${this.responsiveSize};
        background-color: ${cfg.bgColor};
        animation-delay: ${delay};
      `;
      return wave;
    });

    this.wave0 = waves[0];
    this.wave1 = waves[1];
    this.wave2 = waves[2];

    // ── Float wrapper (so float animation doesn't conflict with btn hover) ──
    const floatEl = document.createElement("div");
    if (!cfg.simpleBubble) {
      floatEl.className = "myclone-btn-float";
    }
    this.floatEl = floatEl;

    // ── Main button ────────────────────────────────────────────────────────
    const btn = document.createElement("button");
    btn.className = cfg.simpleBubble
      ? "myclone-btn myclone-btn--simple"
      : "myclone-btn";
    btn.setAttribute(
      "aria-label",
      this.isExpanded ? "Close chat" : cfg.bubbleText || "Open chat",
    );
    btn.style.cssText = `
      width: ${this.responsiveSize};
      height: ${this.responsiveSize};
      background: ${cfg.bgColor};
      box-shadow: 0 4px 20px ${adjustColorOpacity(cfg.bgColor, 0.5)}, 0 2px 8px rgba(0,0,0,0.15);
      border-radius: 9999px !important;
      border: none !important;
      padding: 0 !important;
      margin: 0 !important;
      overflow: hidden !important;
    `;
    btn.addEventListener("click", this.boundHandleClick);
    this.btnEl = btn;

    // ── Tooltip (inside button so it shares the button's position context) ──
    const tooltip = this.buildTooltip();
    this.tooltipEl = tooltip;

    // Initially hidden
    tooltip.style.display = "none";
    btn.appendChild(tooltip);

    // ── Icon slot ──────────────────────────────────────────────────────────
    const iconSlot = document.createElement("div");
    this.iconSlot = iconSlot;
    this.renderIcon(); // populates iconSlot
    btn.appendChild(iconSlot);

    // ── Assemble hierarchy ─────────────────────────────────────────────────
    floatEl.appendChild(btn);

    if (!cfg.simpleBubble) {
      waves.forEach((w) => wrapper.appendChild(w));
    }

    wrapper.appendChild(floatEl);
    outer.appendChild(wrapper);
    this.container.appendChild(outer);

    // Hide waves initially based on current state
    this.updateWavesVisibility();
  }

  // ---------------------------------------------------------------------------
  // Icon rendering
  // ---------------------------------------------------------------------------

  /**
   * Populate the iconSlot with the correct icon element, animated in.
   */
  private renderIcon(): void {
    if (!this.iconSlot) return;

    // Remove previous icon child
    while (this.iconSlot.firstChild) {
      this.iconSlot.removeChild(this.iconSlot.firstChild);
    }

    const { cfg, iconSize } = this;

    if (this.isExpanded) {
      // X / close icon
      const wrap = this.createIconWrap();
      wrap.appendChild(createCloseIcon(cfg.bubbleTextColor, iconSize));
      this.iconSlot.appendChild(wrap);
    } else if (this.currentIconUrl && !this.imageError) {
      // Avatar image
      const wrap = this.createIconWrap(true);
      const img = document.createElement("img");
      img.src = this.currentIconUrl;
      img.alt = "Chat";
      img.className = "myclone-avatar";
      img.addEventListener("error", () => {
        this.imageError = true;
        this.renderIcon(); // fall back to message icon
      });
      wrap.appendChild(img);
      this.iconSlot.appendChild(wrap);
    } else {
      // Default message / chat bubble icon
      const wrap = this.createIconWrap();
      wrap.appendChild(createMessageIcon(cfg.bubbleTextColor, iconSize));
      this.iconSlot.appendChild(wrap);
    }
  }

  private createIconWrap(isAvatar = false): HTMLDivElement {
    const wrap = document.createElement("div");
    wrap.className = isAvatar
      ? "myclone-icon-wrap myclone-icon-wrap--avatar"
      : "myclone-icon-wrap";
    return wrap;
  }

  // ---------------------------------------------------------------------------
  // Tooltip
  // ---------------------------------------------------------------------------

  private buildTooltip(): HTMLDivElement {
    const tooltip = document.createElement("div");
    tooltip.className = "myclone-tooltip";

    const inner = document.createElement("div");
    inner.className = "myclone-tooltip__inner";

    // Sparkles icon
    inner.appendChild(createSparklesIcon("#facc15", 16));

    // Text span
    const span = document.createElement("span");
    span.textContent = this.currentTooltipText();
    inner.appendChild(span);

    // Arrow
    const arrow = document.createElement("div");
    arrow.className = "myclone-tooltip__arrow";
    inner.appendChild(arrow);

    tooltip.appendChild(inner);
    return tooltip;
  }

  private currentTooltipText(): string {
    const messages = this.cfg.tooltipMessages;
    if (!messages || messages.length === 0) return "";
    return messages[this.tooltipIndex % messages.length];
  }

  private updateTooltipText(): void {
    if (!this.tooltipEl) return;
    const span = this.tooltipEl.querySelector("span");
    if (span) {
      span.textContent = this.currentTooltipText();
    }
  }

  private showTooltip(): void {
    if (
      !this.tooltipEl ||
      this.cfg.simpleBubble ||
      this.isExpanded ||
      this.hasInteracted
    )
      return;

    this.tooltipEl.style.display = "flex";
    // Reset animation by forcing a reflow
    this.tooltipEl.classList.remove(
      "myclone-tooltip--enter",
      "myclone-tooltip--exit",
    );
    // Trigger reflow so the browser registers the class removal before re-adding
    void this.tooltipEl.offsetWidth;
    this.tooltipEl.classList.add("myclone-tooltip--enter");
    this.tooltipVisible = true;
  }

  private hideTooltip(animate = true): void {
    if (!this.tooltipEl) return;

    if (!animate) {
      this.tooltipEl.style.display = "none";
      this.tooltipEl.classList.remove(
        "myclone-tooltip--enter",
        "myclone-tooltip--exit",
      );
      this.tooltipVisible = false;
      return;
    }

    this.tooltipEl.classList.remove("myclone-tooltip--enter");
    void this.tooltipEl.offsetWidth;
    this.tooltipEl.classList.add("myclone-tooltip--exit");

    // Hide after animation completes (~200ms)
    const el = this.tooltipEl;
    const onEnd = () => {
      el.style.display = "none";
      el.classList.remove("myclone-tooltip--exit");
      el.removeEventListener("animationend", onEnd);
    };
    el.addEventListener("animationend", onEnd);
    this.tooltipVisible = false;
  }

  // ---------------------------------------------------------------------------
  // Tooltip lifecycle / cycling
  // ---------------------------------------------------------------------------

  /**
   * Start (or restart) the tooltip show/hide/cycle sequence.
   */
  private startTooltipCycle(): void {
    if (this.cfg.simpleBubble || this.hasInteracted) return;

    this.clearAllTimers();

    // Show tooltip after initial 3 s delay
    this.initialTooltipTimer = setTimeout(() => {
      if (this.hasInteracted || this.isExpanded) return;
      this.showTooltip();
      this.scheduleHide();
    }, 3000);
  }

  private scheduleHide(): void {
    // Hide after 4 s
    this.hideTooltipTimer = setTimeout(() => {
      this.hideTooltip();

      // Show again after 8 s with next message
      this.showAgainTimer = setTimeout(() => {
        if (this.hasInteracted || this.isExpanded) return;
        this.tooltipIndex =
          (this.tooltipIndex + 1) % (this.cfg.tooltipMessages.length || 1);
        this.updateTooltipText();
        this.showTooltip();
        this.scheduleHide(); // continue cycling
      }, 8000);
    }, 4000);
  }

  private clearAllTimers(): void {
    if (this.initialTooltipTimer !== null) {
      clearTimeout(this.initialTooltipTimer);
      this.initialTooltipTimer = null;
    }
    if (this.hideTooltipTimer !== null) {
      clearTimeout(this.hideTooltipTimer);
      this.hideTooltipTimer = null;
    }
    if (this.showAgainTimer !== null) {
      clearTimeout(this.showAgainTimer);
      this.showAgainTimer = null;
    }
  }

  // ---------------------------------------------------------------------------
  // Waves & float helpers
  // ---------------------------------------------------------------------------

  private updateWavesVisibility(): void {
    const show = !this.cfg.simpleBubble && !this.isExpanded;
    [this.wave0, this.wave1, this.wave2].forEach((w) => {
      if (!w) return;
      w.style.display = show ? "block" : "none";
    });
  }

  private floatResumeTimer: ReturnType<typeof setTimeout> | null = null;

  private updateFloatAnimation(): void {
    if (!this.floatEl) return;
    const shouldFloat = !this.cfg.simpleBubble && !this.isExpanded;
    if (shouldFloat) {
      // Delay re-adding the float animation so the bubble settles into
      // its collapsed position first, avoiding a visible "jump up".
      if (this.floatResumeTimer) clearTimeout(this.floatResumeTimer);
      this.floatResumeTimer = setTimeout(() => {
        this.floatEl?.classList.add("myclone-btn-float");
        this.floatResumeTimer = null;
      }, 300);
    } else {
      if (this.floatResumeTimer) {
        clearTimeout(this.floatResumeTimer);
        this.floatResumeTimer = null;
      }
      this.floatEl.classList.remove("myclone-btn-float");
    }
  }

  // ---------------------------------------------------------------------------
  // Click handler
  // ---------------------------------------------------------------------------

  private handleClick(): void {
    // Stop tooltip cycle permanently after first interaction
    this.hasInteracted = true;
    this.clearAllTimers();
    this.hideTooltip(false);

    // Update aria-label
    if (this.btnEl) {
      this.btnEl.setAttribute(
        "aria-label",
        this.isExpanded ? this.cfg.bubbleText || "Open chat" : "Close chat",
      );
    }

    this.clickCallback?.();
  }
}
