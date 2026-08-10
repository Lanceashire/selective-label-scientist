/** Public Pi extension entry and shared current-session accessors. */
import workbench from "./ecomic-workbench.impl.ts";

const SESSION_KEY = Symbol.for("ecomic.active-session-id");

export function getActiveSession(): string | undefined {
  return (globalThis as Record<symbol, string | undefined>)[SESSION_KEY];
}

export function setActiveSession(sessionId: string | undefined): void {
  (globalThis as Record<symbol, string | undefined>)[SESSION_KEY] = sessionId;
}

export default workbench;
