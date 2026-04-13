/**
 * Simple postMessage-based parent-child communication
 * Replaces Penpal to avoid ES module iframe issues
 */

export type MessageType =
  | "CHILD_READY"
  | "PARENT_CALL"
  | "CHILD_RESPONSE"
  | "CHILD_CALL"
  | "PARENT_RESPONSE";

export interface Message {
  type: MessageType;
  method?: string;
  args?: unknown[];
  id?: string;
  result?: unknown;
  error?: string;
}

type PromiseResolve = (value: unknown) => void;
type PromiseReject = (reason?: unknown) => void;
type MethodFunction = (...args: unknown[]) => unknown;

export class ParentMessenger<ChildMethods> {
  private iframe: HTMLIFrameElement;
  private pendingCalls = new Map<
    string,
    { resolve: PromiseResolve; reject: PromiseReject }
  >();
  private childReady = false;
  private readyPromise: Promise<void>;
  private readyResolve?: () => void;
  private methods: Record<string, MethodFunction>;

  constructor(
    iframe: HTMLIFrameElement,
    methods: Record<string, MethodFunction>,
  ) {
    this.iframe = iframe;
    this.methods = methods;

    this.readyPromise = new Promise((resolve) => {
      this.readyResolve = resolve;
    });

    window.addEventListener("message", this.handleMessage);
  }

  private handleMessage = (event: MessageEvent) => {
    // CRITICAL: Only handle messages from OUR iframe, not other widgets on the page
    if (event.source !== this.iframe.contentWindow) {
      return; // Not from our iframe
    }

    const message: Message = event.data;

    if (!message || typeof message.type !== "string") {
      return; // Not our message
    }

    switch (message.type) {
      case "CHILD_READY":
        this.childReady = true;
        this.readyResolve?.();
        break;

      case "CHILD_RESPONSE":
        if (message.id) {
          const pending = this.pendingCalls.get(message.id);
          if (pending) {
            if (message.error) {
              pending.reject(new Error(message.error));
            } else {
              pending.resolve(message.result);
            }
            this.pendingCalls.delete(message.id);
          }
        }
        break;

      case "CHILD_CALL":
        this.handleChildCall(message);
        break;
    }
  };

  private async handleChildCall(message: Message) {
    if (!message.method || !message.id) return;

    const method = this.methods[message.method];
    if (!method) {
      this.sendToChild({
        type: "PARENT_RESPONSE",
        id: message.id,
        error: `Method ${message.method} not found`,
      });
      return;
    }

    try {
      const result = await method(...(message.args || []));
      this.sendToChild({
        type: "PARENT_RESPONSE",
        id: message.id,
        result,
      });
    } catch (error: unknown) {
      this.sendToChild({
        type: "PARENT_RESPONSE",
        id: message.id,
        error: error instanceof Error ? error.message : String(error),
      });
    }
  }

  private sendToChild(message: Message) {
    if (!this.iframe.contentWindow) return;
    this.iframe.contentWindow.postMessage(message, "*");
  }

  async waitForReady(): Promise<void> {
    return this.readyPromise;
  }

  async call<K extends keyof ChildMethods>(
    method: K,
    ...args: unknown[]
  ): Promise<unknown> {
    await this.waitForReady();

    const id = `${Date.now()}-${Math.random()}`;
    const promise = new Promise((resolve, reject) => {
      this.pendingCalls.set(id, { resolve, reject });

      // Timeout after 10 seconds
      setTimeout(() => {
        if (this.pendingCalls.has(id)) {
          this.pendingCalls.delete(id);
          reject(new Error(`Call to ${String(method)} timed out`));
        }
      }, 10000);
    });

    this.sendToChild({
      type: "PARENT_CALL",
      method: String(method),
      args,
      id,
    });

    return promise;
  }

  destroy() {
    window.removeEventListener("message", this.handleMessage);
    this.pendingCalls.clear();
  }
}

export class ChildMessenger<ParentMethods> {
  private pendingCalls = new Map<
    string,
    { resolve: PromiseResolve; reject: PromiseReject }
  >();
  private methods: Record<string, MethodFunction>;
  private parentReady = false;
  private readyInterval: ReturnType<typeof setInterval> | null = null;

  constructor(methods: Record<string, MethodFunction>) {
    this.methods = methods;
    window.addEventListener("message", this.handleMessage);

    // Notify parent we're ready - send multiple times to handle race conditions
    this.sendToParent({ type: "CHILD_READY" });

    // Keep sending ready signal until we receive a response from parent
    this.readyInterval = setInterval(() => {
      if (!this.parentReady) {
        this.sendToParent({ type: "CHILD_READY" });
      } else if (this.readyInterval) {
        clearInterval(this.readyInterval);
        this.readyInterval = null;
      }
    }, 100);

    // Stop after 10 seconds
    setTimeout(() => {
      if (this.readyInterval) {
        clearInterval(this.readyInterval);
        this.readyInterval = null;
      }
    }, 10000);
  }

  private handleMessage = (event: MessageEvent) => {
    // Only handle messages from parent window (allow same window for inline mode)
    if (event.source !== window.parent && event.source !== window) {
      return; // Not from our parent
    }

    const message: Message = event.data;

    if (!message || typeof message.type !== "string") {
      return;
    }

    switch (message.type) {
      case "PARENT_CALL":
        this.parentReady = true; // Parent is communicating, stop sending ready signals
        this.handleParentCall(message);
        break;

      case "PARENT_RESPONSE":
        this.parentReady = true; // Parent is communicating, stop sending ready signals
        if (message.id) {
          const pending = this.pendingCalls.get(message.id);
          if (pending) {
            if (message.error) {
              pending.reject(new Error(message.error));
            } else {
              pending.resolve(message.result);
            }
            this.pendingCalls.delete(message.id);
          }
        }
        break;
    }
  };

  private async handleParentCall(message: Message) {
    if (!message.method || !message.id) return;

    const method = this.methods[message.method];
    if (!method) {
      this.sendToParent({
        type: "CHILD_RESPONSE",
        id: message.id,
        error: `Method ${message.method} not found`,
      });
      return;
    }

    try {
      const result = await method(...(message.args || []));
      this.sendToParent({
        type: "CHILD_RESPONSE",
        id: message.id,
        result,
      });
    } catch (error: unknown) {
      this.sendToParent({
        type: "CHILD_RESPONSE",
        id: message.id,
        error: error instanceof Error ? error.message : String(error),
      });
    }
  }

  private sendToParent(message: Message) {
    if (!window.parent) return;
    window.parent.postMessage(message, "*");
  }

  async call<K extends keyof ParentMethods>(
    method: K,
    ...args: unknown[]
  ): Promise<unknown> {
    const id = `${Date.now()}-${Math.random()}`;
    const promise = new Promise((resolve, reject) => {
      this.pendingCalls.set(id, { resolve, reject });

      setTimeout(() => {
        if (this.pendingCalls.has(id)) {
          this.pendingCalls.delete(id);
          reject(new Error(`Call to ${String(method)} timed out`));
        }
      }, 10000);
    });

    this.sendToParent({
      type: "CHILD_CALL",
      method: String(method),
      args,
      id,
    });

    return promise;
  }

  destroy() {
    if (this.readyInterval) {
      clearInterval(this.readyInterval);
      this.readyInterval = null;
    }
    window.removeEventListener("message", this.handleMessage);
    this.pendingCalls.clear();
  }
}
