/** The raw payload shape sent by the backend agent on "content_output" topic */
export interface ContentOutputPayload {
  type: "content_output";
  content_type: string; // e.g. "blog", "report", "article"
  title: string;
  body: string; // raw markdown
  persona_name?: string;
  persona_role?: string;
}

/** Stored representation used by UI components */
export interface ContentOutputItem {
  id: string;
  content_type: string;
  title: string;
  body: string;
  persona_name?: string;
  persona_role?: string;
  receivedAt: number;
}
