// WebSocket 客户端占位。见 Start.md §12。
import type { Envelope } from "../../../../packages/protocol/src/messages";

export class GameSocket {
  constructor(private url: string) {}
  connect(): void {/* TODO Phase 3 */}
  send<P>(_msg: Envelope<P>): void {/* TODO */}
  onMessage(_cb: (msg: Envelope) => void): void {/* TODO */}
}
