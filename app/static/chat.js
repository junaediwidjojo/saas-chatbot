const form = document.querySelector('#chat-form');
const input = document.querySelector('#message');
const messages = document.querySelector('#messages');
const send = document.querySelector('#send');
const clear = document.querySelector('#clear');
const status = document.querySelector('#status');
const error = document.querySelector('#error');
const suggestions = document.querySelectorAll('[data-question]');
let busy = false;
let idleStatus = 'Ready for a question';
// Retain validated metadata for application logic; this is page-local, not model memory.
const assistantResponses = [];
const conversationHistory = [];
let conversationSummary = '';
let memoryLimits = null;
let productName = 'our product';

function rememberExchange(question, answer) {
  conversationHistory.push({ role: 'user', content: question }, { role: 'assistant', content: answer });
}

function needsSummary() {
  const encoder = new TextEncoder();
  const characters = conversationHistory.reduce((total, item) => total + Array.from(item.content).length, 0);
  const bytes = encoder.encode(conversationSummary).length +
    conversationHistory.reduce((total, item) => total + encoder.encode(item.content).length, 0);
  const estimate = Math.ceil(bytes / memoryLimits.token_estimate_bytes);
  return conversationHistory.length > memoryLimits.history_messages ||
    characters > memoryLimits.history_characters || estimate > memoryLimits.summary_trigger_tokens;
}

async function updateSummary() {
  if (!needsSummary() || conversationHistory.length < 4) return;
  status.textContent = 'Updating conversation context…';
  const response = await fetch('/memory/summarize', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ summary: conversationSummary, history: conversationHistory }),
    signal: AbortSignal.timeout(45000),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Could not update conversation context. Please retry.');
  if (typeof data.summary !== 'string' || !data.summary.trim() ||
      Array.from(data.summary).length > memoryLimits.summary_characters || !Array.isArray(data.history)) {
    throw new Error('The summary format was invalid. Your history has been kept.');
  }
  const remaining = data.history;
  const removed = conversationHistory.length - remaining.length;
  if (removed < 2 || removed % 2 !== 0 || remaining.length < 2 ||
      remaining.length > memoryLimits.history_messages ||
      remaining.some((item, index) => item.role !== conversationHistory[removed + index].role ||
        item.content !== conversationHistory[removed + index].content) ||
      remaining.reduce((total, item) => total + Array.from(item.content).length, 0) > memoryLimits.history_characters) {
    throw new Error('The summary history was invalid. Your history has been kept.');
  }
  // Commit both pieces together only after the entire response has been checked.
  conversationSummary = data.summary;
  conversationHistory.splice(0, removed);
}

function addMessage(role, text, response = null) {
  const article = document.createElement('article');
  article.className = `message ${role}`;
  const speaker = document.createElement('p');
  speaker.className = 'speaker';
  speaker.textContent = role === 'user' ? 'YOU' : 'ASSISTANT';
  const bubble = document.createElement('p');
  bubble.className = 'bubble';
  // Treat both customer input and model output as text, never executable HTML.
  bubble.textContent = text;
  article.append(speaker, bubble);
  if (response && Array.isArray(response.citations) && response.citations.length) {
    const sources = document.createElement('p');
    sources.className = 'source-note';
    sources.textContent = 'Sources: ' + response.citations.map(citation =>
      `${citation.section} (version ${citation.version.slice(0, 8)})`).join('; ');
    article.append(sources);
  }
  if (response) {
    article.dataset.intent = response.intent;
    if (response.requires_human) {
      const note = document.createElement('p');
      note.className = 'support-note';
      note.textContent = 'Human support recommended. No ticket has been created.';
      article.append(note);
    }
  }
  messages.append(article);
  messages.scrollTop = messages.scrollHeight;
  return article;
}

function setBusy(value) {
  busy = value;
  send.disabled = clear.disabled = input.disabled = value;
  suggestions.forEach((button) => { button.disabled = value; });
  status.textContent = value ? 'Thinking…' : idleStatus;
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (busy) return;
  const message = input.value.trim();
  if (!message) {
    input.setCustomValidity('Please type a message.');
    input.reportValidity();
    return;
  }
  error.hidden = true;
  const userMessage = addMessage('user', message);
  input.value = '';
  setBusy(true);
  try {
    await configurationReady;
    if (!memoryLimits) await checkConfiguration();
    if (!memoryLimits) throw new Error('Cannot load conversation settings. Check the server and retry.');
    await updateSummary();
    status.textContent = 'Thinking…';
    const response = await fetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, history: conversationHistory, summary: conversationSummary }),
      signal: AbortSignal.timeout(45000),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'The request failed. Please try again.');
    if (typeof data.answer !== 'string' || !data.answer.trim()) throw new Error('No reply was received. Please try again.');
    if (typeof data.intent !== 'string' || typeof data.requires_human !== 'boolean') throw new Error('The reply format was invalid. Please try again.');
    assistantResponses.push(data);
    addMessage('assistant', data.answer, data);
    rememberExchange(message, data.answer);
  } catch (failure) {
    userMessage.remove();
    input.value = message;
    error.textContent = failure.name === 'TimeoutError'
      ? 'The request timed out. Your message is ready to retry.'
      : failure instanceof TypeError || failure instanceof SyntaxError
        ? 'Cannot reach the chat server. Check that it is running and try again.'
        : failure.message;
    error.hidden = false;
  } finally {
    setBusy(false);
    input.focus();
  }
});

input.addEventListener('input', () => input.setCustomValidity(''));
input.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    form.requestSubmit();
  }
});

suggestions.forEach((button) => button.addEventListener('click', () => {
  input.value = button.dataset.question;
  input.setCustomValidity('');
  input.focus();
}));

clear.addEventListener('click', () => {
  assistantResponses.length = 0;
  conversationHistory.length = 0;
  conversationSummary = '';
  messages.replaceChildren();
  addMessage('assistant', `Hi! I can help with ${productName}. What would you like to know?`);
  input.value = '';
  input.setCustomValidity('');
  error.hidden = true;
  input.focus();
});

async function checkConfiguration() {
  try {
    const response = await fetch('/health', { signal: AbortSignal.timeout(5000) });
    if (!response.ok) throw new Error();
    const health = await response.json();
    memoryLimits = health.memory_limits;
    productName = health.product_name || 'our product';
    document.querySelector('.description').textContent = `Ask about ${productName}. Answers use the selected knowledge and show supporting sources.`;
    const welcome = document.querySelector('#welcome');
    if (welcome) welcome.textContent = `Hi! I can help with ${productName}. What would you like to know?`;
    idleStatus = health.configured ? 'Ready for a question' : 'Setup needed';
    if (health.configured && health.rag_ready === false) {
      idleStatus = 'Knowledge setup needed';
      error.textContent = 'The knowledge index needs setup or refresh. See the README for ingestion instructions.';
      error.hidden = false;
    }
    if (!health.configured) {
      error.textContent = 'Add your provider API key to .env and restart the server to begin.';
      error.hidden = false;
    }
  } catch {
    idleStatus = 'Server unavailable';
  }
  if (!busy) status.textContent = idleStatus;
}

const configurationReady = checkConfiguration();
