// WebSocket 客户端占位。见 Start.md §12。
import type { Envelope } from "../../../../packages/protocol/src/messages";

export class GameSocket {
  readonly url: string;
  constructor(url: string) {
    this.url = url;
  }
  connect(): void {
    /* TODO Phase 3: new WebSocket(this.url) */
  }
  send<P>(_msg: Envelope<P>): void {
    /* TODO Phase 3 */
  }
  onMessage(_cb: (msg: Envelope) => void): void {
    /* TODO Phase 3 */
  }
}
