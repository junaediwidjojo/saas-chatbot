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

function addMessage(role, text) {
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
    const response = await fetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message }),
      signal: AbortSignal.timeout(45000),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'The request failed. Please try again.');
    if (typeof data.answer !== 'string' || !data.answer.trim()) throw new Error('No reply was received. Please try again.');
    addMessage('assistant', data.answer);
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
  messages.replaceChildren();
  addMessage('assistant', 'Hi there! I’m the SaaS support assistant. What would you like to know?');
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
    idleStatus = health.configured ? 'Ready for a question' : 'Setup needed';
    if (!health.configured) {
      error.textContent = 'Add OPENAI_API_KEY to your .env file and restart the server to begin.';
      error.hidden = false;
    }
  } catch {
    idleStatus = 'Server unavailable';
  }
  if (!busy) status.textContent = idleStatus;
}

checkConfiguration();
