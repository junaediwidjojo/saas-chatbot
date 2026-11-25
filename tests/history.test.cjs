const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const { test } = require('node:test');
const vm = require('node:vm');

const source = readFileSync(join(__dirname, '../app/static/chat.js'), 'utf8');

function element() {
  return {
    value: '', hidden: true, disabled: false, dataset: {}, children: [], listeners: {},
    append(...children) {
      this.children.push(...children);
    },
    replaceChildren() {
      this.children = [];
    },
    remove() {},
    focus() {},
    setCustomValidity() {},
    reportValidity() {},
    addEventListener(name, handler) {
      this.listeners[name] = handler;
    },
  };
}

async function browserHarness() {
  const nodes = new Map();
  const calls = [];
  const state = { summaryFailure: false, chatFailure: false, invalidSummary: false, citations: [], identification: null };
  const context = vm.createContext({
    TextEncoder, AbortSignal, FormData, File,
    document: {
      querySelector(selector) {
        if (!nodes.has(selector)) nodes.set(selector, element());
        return nodes.get(selector);
      },
      querySelectorAll() {
        return [];
      },
      createElement: element,
    },
    async fetch(url, options) {
      const multipart = options?.body instanceof FormData;
      const body = multipart
        ? { ...JSON.parse(options.body.get('payload')), image: options.body.get('image') }
        : options?.body ? JSON.parse(options.body) : null;
      const response = (ok, data) => ({ ok, async json() { return data; } });
      if (url === '/health') return response(true, { configured: true, memory_limits: {
        history_messages: 10, history_characters: 16000, summary_characters: 2000,
        summary_trigger_tokens: 3000, token_estimate_bytes: 3, message_characters: 4000,
      }, image_upload: { enabled: true, max_bytes: 5242880, types: ['image/png', 'image/jpeg', 'image/webp'] } });
      calls.push({ url, body });
      if (url === '/memory/summarize') {
        if (state.summaryFailure) return response(false, { detail: 'Summary unavailable; retry.' });
        return response(true, {
          summary: `Updated: ${body.summary || 'earlier context'}`,
          history: state.invalidSummary ? body.history : body.history.slice(body.history.length > 4 ? -4 : -2),
        });
      }
      if (state.chatFailure) return response(false, { detail: 'Chat unavailable; retry.' });
      const reply = { intent: 'product', answer: 'Displayed demo answer.', requires_human: false, confidence: null, citations: state.citations };
      return response(true, multipart ? { ...reply, identification: state.identification } : reply);
    },
  });
  vm.runInContext(source, context);
  await vm.runInContext('configurationReady', context);
  return {
    calls, state,
    async send(message) {
      nodes.get('#message').value = message;
      await nodes.get('#chat-form').listeners.submit({ preventDefault() {} });
    },
    clear() {
      nodes.get('#clear').listeners.click();
    },
    choosePhoto(file) {
      nodes.get('#photo').files = [file];
      nodes.get('#photo').listeners.change();
    },
    node(selector) {
      return nodes.get(selector);
    },
    notes(className) {
      return nodes.get('#messages').children.flatMap(article => article.children)
        .filter(child => child.className === className).map(child => child.textContent);
    },
    snapshot() {
      return JSON.parse(vm.runInContext('JSON.stringify({summary:conversationSummary, history:conversationHistory})', context));
    },
    draft() {
      return nodes.get('#message').value;
    },
    displayedSources() {
      return nodes.get('#messages').children.flatMap(article => article.children)
        .filter(child => child.className === 'source-note').map(child => child.textContent);
    },
  };
}

test('older pairs are summarized before chat and subsequent summaries carry previous context', async () => {
  const app = await browserHarness();
  for (let i = 0; i < 6; i++) await app.send(`Question ${i}`);
  assert.equal(app.snapshot().history.length, 12); // No discard before a successful summary.
  await app.send('Follow-up');
  const update = app.calls.find(call => call.url === '/memory/summarize');
  assert.equal(update.body.history.length, 12);
  const chat = app.calls.at(-1).body;
  assert.equal(chat.history.length, 4);
  assert.equal(chat.history[0].content, 'Question 4');
  assert.equal(chat.summary, 'Updated: earlier context');
  assert.deepEqual(Object.keys(chat.history[1]).sort(), ['content', 'role']);
  for (let i = 0; i < 4; i++) await app.send(`Next ${i}`);
  const updates = app.calls.filter(call => call.url === '/memory/summarize');
  assert.equal(updates.length, 2);
  assert.equal(updates[1].body.summary, 'Updated: earlier context');
});

test('failed or invalid summaries preserve history and draft; retry does not duplicate messages', async () => {
  for (const failure of ['summaryFailure', 'invalidSummary']) {
    const app = await browserHarness();
    for (let i = 0; i < 6; i++) await app.send(`Question ${i}`);
    const before = app.snapshot();
    app.state[failure] = true;
    await app.send('Pending question');
    assert.deepEqual(app.snapshot(), before);
    assert.equal(app.draft(), 'Pending question');
    assert.equal(app.calls.at(-1).url, '/memory/summarize');
    app.state[failure] = false;
    await app.send('Pending question');
    assert.equal(app.snapshot().history.filter(item => item.content === 'Pending question').length, 1);
  }
});

test('a chat failure after successful summarization retains the new summary for retry', async () => {
  const app = await browserHarness();
  for (let i = 0; i < 6; i++) await app.send(`Question ${i}`);
  app.state.chatFailure = true;
  await app.send('Pending');
  assert.equal(app.snapshot().summary, 'Updated: earlier context');
  assert.equal(app.snapshot().history.length, 4);
  app.state.chatFailure = false;
  await app.send('Pending');
  assert.equal(app.calls.filter(call => call.url === '/memory/summarize').length, 1);
  assert.equal(app.snapshot().history.length, 6);
});

test('size trigger runs before the exchange limit; reset clears summary and history', async () => {
  const app = await browserHarness();
  await app.send('😀'.repeat(3000));
  await app.send('😀'.repeat(3000));
  await app.send('Follow-up');
  assert.equal(app.calls.filter(call => call.url === '/memory/summarize').length, 1);
  assert.notEqual(app.snapshot().summary, '');
  app.clear();
  assert.deepEqual(app.snapshot(), { summary: '', history: [] });
  const freshPage = await browserHarness();
  assert.deepEqual(freshPage.snapshot(), { summary: '', history: [] });
});

test('citations are displayed as text and excluded from conversation memory', async () => {
  const app = await browserHarness();
  app.state.citations = [{ id: 'chunk-1', section: '<img src=x onerror=alert(1)>', version: 'abcdef012345' }];
  await app.send('What are the plans?');
  assert.deepEqual(app.displayedSources(), ['Sources: <img src=x onerror=alert(1)> (version abcdef01)']);
  assert.equal(app.snapshot().history[1].content, 'Displayed demo answer.');
  await app.send('What about Gold?');
  assert.deepEqual(Object.keys(app.calls.at(-1).body.history[1]).sort(), ['content', 'role']);
});

test('a photo is sent as multipart, noted in memory, and cleared only after success', async () => {
  const app = await browserHarness();
  const photo = new File([new Uint8Array([137, 80, 78, 71])], 'printer.png', { type: 'image/png' });
  app.choosePhoto(photo);
  assert.equal(app.node('#attachment').hidden, false);
  app.state.chatFailure = true;
  await app.send('');
  assert.equal(app.calls.at(-1).url, '/chat/image');
  assert.equal(app.node('#attachment').hidden, false); // Retry keeps the photo.
  assert.equal(app.draft(), '');
  app.state.chatFailure = false;
  app.state.identification = { status: 'identified', product_name: 'DemoPrint TP-58', candidate_names: [], manual_available: true };
  app.state.citations = [{ id: 'p2', title: 'Panduan DemoPrint TP-58', section: 'Panduan DemoPrint TP-58 > Halaman 2', version: 'abcdef012345', page: 2 }];
  await app.send('Cara pairing?');
  const request = app.calls.at(-1);
  assert.equal(request.url, '/chat/image');
  assert.equal(request.body.message, 'Cara pairing?');
  assert.equal(request.body.image.name, 'printer.png');
  assert.deepEqual(app.displayedSources(), ['Sources: Panduan DemoPrint TP-58, p. 2 (version abcdef01)']);
  assert.match(app.notes('photo-note').join(' '), /Photo attached: printer\.png.*looks like DemoPrint TP-58/);
  assert.equal(app.snapshot().history[0].content, 'Cara pairing?\n[Foto terlampir: dikenali sebagai DemoPrint TP-58]');
  assert.equal(app.node('#attachment').hidden, true);
  await app.send('Dan lampu merah?');
  assert.equal(app.calls.at(-1).url, '/chat');
});

test('photo-only sends use a default question; unsupported files are refused locally', async () => {
  const app = await browserHarness();
  app.choosePhoto(new File(['%PDF'], 'manual.pdf', { type: 'application/pdf' }));
  assert.equal(app.node('#attachment').hidden, true);
  assert.match(app.node('#error').textContent, /PNG, JPEG, or WebP/);
  app.state.identification = { status: 'ambiguous', candidate_names: ['DemoPrint TP-58', 'DemoPrint TP-80'] };
  app.choosePhoto(new File(['x'], 'unclear.jpg', { type: 'image/jpeg' }));
  await app.send('');
  assert.match(app.calls.at(-1).body.message, /Produk apa ini/);
  assert.match(app.snapshot().history[0].content, /model belum pasti — DemoPrint TP-58 atau DemoPrint TP-80/);
  app.choosePhoto(new File(['x'], 'again.jpg', { type: 'image/jpeg' }));
  app.clear();
  assert.equal(app.node('#attachment').hidden, true);
});
