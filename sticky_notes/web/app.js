'use strict';
const $ = id => document.getElementById(id);
const fragment = new URLSearchParams(location.hash.slice(1));
const incomingToken = fragment.get('token');
if (incomingToken) sessionStorage.setItem('sticky-token', incomingToken);
const token = incomingToken || sessionStorage.getItem('sticky-token') || '';
let requestedNote = fragment.get('note');
history.replaceState(null, '', location.pathname);
let notes = [], editing = null, filter = 'all', busy = false, dirty = false, stopped = false;
let refreshSequence = 0, rendered = '';
for (const [id, max] of [['hours', 24], ['minutes', 60]]) {
  for (let value = 1; value <= max; value++) $(id).add(new Option(String(value), String(value)));
}

// Calls are queued so simultaneous prompts cannot replace one another.
// Resolves to a button label, or null when dismissed with Escape.
let dialogQueue = Promise.resolve();
function dialog(buttons, text) {
  const show = () => new Promise(resolve => {
    const modal = document.createElement('dialog');
    modal.className = 'prompt-dialog';
    modal.setAttribute('aria-labelledby', 'prompt-title');
    modal.setAttribute('aria-describedby', 'prompt-text');
    const heading = document.createElement('h2');
    heading.id = 'prompt-title';
    heading.textContent = 'Sticky notes';
    const prompt = document.createElement('p');
    prompt.id = 'prompt-text';
    prompt.textContent = text;
    const actions = document.createElement('div');
    actions.className = 'prompt-actions';
    let result = null;
    for (const label of buttons) {
      const control = document.createElement('button');
      control.type = 'button';
      control.textContent = label;
      control.className = ['Delete', 'Discard', 'Quit'].includes(label) ? 'danger' : 'quiet';
      control.autofocus = label === 'Cancel' || buttons.length === 1;
      control.addEventListener('click', () => { result = label; modal.close(); });
      actions.append(control);
    }
    modal.append(heading, prompt, actions);
    modal.addEventListener('keydown', event => {
      if (event.key !== 'Tab') return;
      const controls = [...actions.querySelectorAll('button')];
      const index = controls.indexOf(document.activeElement);
      event.preventDefault();
      controls[(index + (event.shiftKey ? -1 : 1) + controls.length) % controls.length]?.focus();
    });
    modal.addEventListener('close', () => { modal.remove(); resolve(result); }, {once:true});
    document.body.append(modal);
    modal.showModal();
  });
  const pending = dialogQueue.then(show);
  dialogQueue = pending.catch(() => {});
  return pending;
}

function error(message) {
  $('error').textContent = message || '';
  $('error').hidden = !message;
}
async function api(path, data) {
  const response = await fetch(path, {
    method: data ? 'POST' : 'GET',
    headers: {Authorization: `Bearer ${token}`, ...(data ? {'Content-Type': 'application/json'} : {})},
    ...(data ? {body: JSON.stringify(data)} : {})
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'The app could not complete this request.');
  return result;
}
function setBusy(value) {
  busy = value;
  document.querySelectorAll('button').forEach(button => {
    if (!button.closest('dialog')) button.disabled = value;
  });
}
async function mutate(command, payload, after) {
  if (busy) return;
  setBusy(true);
  error('');
  ++refreshSequence;
  try {
    const result = await api('/api/command', {command, payload});
    if (after) after(result);
    if (!stopped) await refresh();
  } catch (reason) {
    error(reason.message || 'Cannot reach the app. Check that it is still running.');
  } finally {
    setBusy(false);
  }
}
function reminderText(note) {
  if (note.alert) return 'Reminder is ringing';
  if (note.deadline) return `Reminder ${new Date(note.deadline * 1000).toLocaleString([], {month:'short', day:'numeric', hour:'numeric', minute:'2-digit'})}`;
  return note.visible ? 'On your desktop' : 'Hidden from desktop';
}
function inkFor(color) {
  const rgb = [1,3,5].map(index => parseInt(color.slice(index, index+2),16));
  return rgb[0]*.299 + rgb[1]*.587 + rgb[2]*.114 > 145 ? '#202d32' : '#ffffff';
}
function button(text, action, className='') {
  const element = document.createElement('button');
  element.type = 'button';
  element.textContent = text;
  element.className = className;
  element.disabled = busy;
  element.addEventListener('click', action);
  return element;
}
function render() {
  const signature = JSON.stringify([notes, filter, editing]);
  if (signature === rendered) return;
  rendered = signature;
  const visibleCount = notes.filter(note => note.visible).length;
  $('count').textContent = `${notes.length} ${notes.length === 1 ? 'note' : 'notes'} / ${visibleCount} on desktop`;
  const shown = notes.filter(note => filter === 'all' || (filter === 'visible' ? note.visible : !note.visible));
  $('notes').replaceChildren();
  $('empty').hidden = !!shown.length;
  $('empty').querySelector('h3').textContent = notes.length ? 'Nothing in this view.' : 'A clear desk. A fresh start.';
  $('empty').querySelector('p').textContent = notes.length ? 'Switch to All to see your other notes.' : 'Create a note here. It will float on your desktop, ready whenever you need it.';
  for (const note of shown) {
    const card = document.createElement('article');
    card.className = `note-card${editing === note.id ? ' selected' : ''}${note.alert ? ' alert' : ''}`;
    card.style.backgroundColor = note.color;
    card.style.color = inkFor(note.color);
    const title = document.createElement('h3');
    title.textContent = note.title || 'Untitled note';
    const body = document.createElement('p');
    body.className = 'note-text';
    body.textContent = note.body || 'A little space, ready for a thought.';
    const meta = document.createElement('p');
    meta.className = 'note-meta';
    meta.textContent = reminderText(note);
    const actions = document.createElement('div');
    actions.className = 'card-actions';
    actions.append(button('Edit', () => selectNote(note)), button(note.visible ? 'Hide' : 'Show', () => mutate('visibility', {id:note.id, visible:!note.visible})));
    if (note.alert) actions.append(button('Dismiss', () => mutate('dismiss', {id:note.id})), button('Snooze 5m', () => mutate('snooze', {id:note.id})));
    else if (note.deadline) actions.append(button('Cancel timer', () => mutate('cancel', {id:note.id})));
    actions.append(button('Delete', async () => {
      if (await dialog(['Delete', 'Cancel'], `Delete “${note.title || 'Untitled note'}”? This cannot be undone.`) === 'Delete') {
        mutate('delete', {id:note.id}, () => {if(editing === note.id) resetEditor();});
      }
    }, 'delete'));
    card.append(title, body, meta, actions);
    $('notes').append(card);
  }
}
function colorSelected(value) {
  $('color').value = value;
  document.querySelectorAll('[data-color]').forEach(element => element.setAttribute('aria-pressed', String(element.dataset.color === value.toLowerCase())));
}
function markDirty() {
  dirty = true;
  $('draft-state').textContent = 'Unsaved changes';
}
async function canReplaceDraft() {
  return !dirty || await dialog(['Discard', 'Cancel'], 'Discard your unsaved changes?') === 'Discard';
}
function resetEditor() {
  editing = null;
  dirty = false;
  HTMLFormElement.prototype.reset.call($('note-form'));
  colorSelected('#fff2a8');
  $('editor-title').textContent = 'A fresh note';
  $('draft-state').textContent = 'Not saved yet';
  $('save').textContent = 'Create note';
  $('reset').textContent = 'Clear';
  $('reminder-mode').options[0].textContent = 'No reminder';
  $('timer-status').textContent = 'A reminder shows the note, highlights it, and beeps.';
  timerFields();
  render();
}
async function selectNote(note, force=false) {
  if (!force && !await canReplaceDraft()) return;
  editing = note.id;
  dirty = false;
  $('title').value = note.title;
  $('body').value = note.body;
  colorSelected(note.color);
  $('reminder-mode').value = 'keep';
  $('reminder-mode').options[0].textContent = 'Keep current reminder';
  $('timer-status').textContent = note.alert || note.deadline ? reminderText(note) : 'No reminder set.';
  $('editor-title').textContent = 'Edit note';
  $('draft-state').textContent = 'Saved on your computer';
  $('save').textContent = 'Save changes';
  $('reset').textContent = 'New note';
  timerFields();
  render();
  if (!force) $('title').focus();
}
function timerFields() {
  const show = $('reminder-mode').value === 'set';
  $('timer-fields').hidden = !show;
  $('hours').disabled = !show;
  $('minutes').disabled = !show;
}
async function refresh() {
  const sequence = ++refreshSequence;
  try {
    const result = await api('/api/notes');
    if (sequence !== refreshSequence || stopped) return;
    notes = result;
    const current = notes.find(note => note.id === editing);
    if (current) $('timer-status').textContent = current.alert || current.deadline ? reminderText(current) : 'No reminder set.';
    $('connection').textContent = 'Connected to your desktop';
    render();
    if (requestedNote) {
      const note = notes.find(n => n.id === requestedNote);
      if (note) selectNote(note, true);
      requestedNote = null;
    }
  } catch (reason) {
    if (sequence !== refreshSequence || stopped) return;
    $('connection').textContent = 'Disconnected';
    error(reason.message || 'Cannot reach the app. Check that it is still running.');
  }
}
$('note-form').addEventListener('input', markDirty);
$('note-form').addEventListener('change', markDirty);
$('note-form').addEventListener('submit', event => {
  event.preventDefault();
  const payload = {title:$('title').value, body:$('body').value, color:$('color').value};
  if (editing) payload.id = editing;
  if ($('reminder-mode').value === 'set') {
    payload.minutes = Number($('hours').value) * 60 + Number($('minutes').value);
    if (payload.minutes < 1) {
      error('Choose at least 1 minute for your timer.');
      $('minutes').focus();
      return;
    }
  }
  if ($('reminder-mode').value === 'cancel') payload.minutes = null;
  // Freeze the form while saving so the response cannot erase subsequent typing.
  const inputs = [...$('note-form').querySelectorAll('input,textarea,select')];
  inputs.forEach(input => input.disabled = true);
  mutate(editing ? 'update' : 'create', payload, note => selectNote(note, true)).finally(() => {
    inputs.forEach(input => input.disabled = false);
    timerFields();
  });
});
$('new-note').addEventListener('click', async () => {if(await canReplaceDraft()){resetEditor();$('title').focus();}});
$('reset').addEventListener('click', async () => {if(await canReplaceDraft()) resetEditor();});
$('color').addEventListener('input', () => colorSelected($('color').value));
$('reminder-mode').addEventListener('change', timerFields);
document.querySelectorAll('[data-color]').forEach(element => element.addEventListener('click', () => {colorSelected(element.dataset.color);markDirty();}));
document.querySelectorAll('[data-filter]').forEach(element => element.addEventListener('click', () => {
  filter = element.dataset.filter;
  document.querySelectorAll('[data-filter]').forEach(button => button.setAttribute('aria-pressed', String(button === element)));
  render();
}));
$('show-all').addEventListener('click', () => mutate('visibility_all', {visible:true}));
$('hide-all').addEventListener('click', () => mutate('visibility_all', {visible:false}));
$('quit').addEventListener('click', async () => {
  if (await dialog(['Quit', 'Cancel'], 'Quit Sticky Notes and close all note windows? Your notes stay saved. Reminders resume when you restart.' + (dirty ? ' Your unsaved draft will be lost.' : '')) !== 'Quit') return;
  mutate('shutdown', {}, () => {stopped=true;dirty=false;$('connection').textContent='App stopped';$('note-form').querySelectorAll('input,textarea,select').forEach(input => input.disabled=true);});
});
window.addEventListener('beforeunload', event => {if(dirty){event.preventDefault();event.returnValue='';}});
resetEditor();
refresh();
setInterval(() => {if(!busy && !stopped) refresh();}, 2000);
