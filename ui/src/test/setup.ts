import '@testing-library/jest-dom'
import { vi } from 'vitest'

// Mock WebSocket
class MockWebSocket {
  url: string;
  onmessage: ((ev: any) => any) | null = null;
  onopen: (() => any) | null = null;
  onclose: (() => any) | null = null;
  readyState: number = 1;
  static instances: MockWebSocket[] = [];

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
    setTimeout(() => this.onopen?.(), 0);
  }

  send(data: string) {
    console.log('MockWS Send:', data);
    const msg = JSON.parse(data);
    if (msg.type === 'set_mode') {
      setTimeout(() => {
        this.onmessage?.({ data: JSON.stringify({ type: 'mode_updated', mode: msg.mode }) } as any);
      }, 0);
    }
  }

  close() {
    this.onclose?.();
  }
}

vi.stubGlobal('WebSocket', MockWebSocket);

// Fix for JSDOM missing scrollTo
Element.prototype.scrollTo = vi.fn();
