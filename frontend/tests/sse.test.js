import test from 'node:test';
import assert from 'node:assert/strict';
import { streamChat, setApiToken } from '../src/utils/sse.js';

function mockStream(chunks, status = 200) {
  globalThis.fetch = async (url, options) => {
    assert.equal(url, '/api/chat/stream');
    assert.equal(options.headers.get('Authorization'), 'Bearer test-token');
    assert.equal(options.method, 'POST');
    return new Response(new ReadableStream({ start(controller) {
      for (const chunk of chunks) controller.enqueue(new TextEncoder().encode(chunk));
      controller.close();
    }}), {status});
  };
}
test('stream handles split frames, CRLF and authenticated requests', async () => {
  setApiToken('test-token');
  mockStream(['data: {"type":"to', 'ken","content":"hello"}\r', '\n\r\ndata: {"type":"end"}\n\n']);
  const tokens = [];
  await new Promise((resolve, reject) => streamChat('question', {
    onToken: token => tokens.push(token), onEnd: resolve, onError: reject,
  }));
  assert.deepEqual(tokens, ['hello']);
});
test('premature EOF reports failure', async () => {
  mockStream(['data: {"type":"start"}\n\n']);
  const error = await new Promise(resolve => streamChat('question', {onError: resolve}));
  assert.match(error, /before completion/);
});
test('HTTP authentication failure reports failure', async () => {
  mockStream([], 401);
  const error = await new Promise(resolve => streamChat('question', {onError: resolve}));
  assert.match(error, /401/);
});
