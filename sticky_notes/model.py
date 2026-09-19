"""Validated, transactional note storage. Only used by the Tk thread."""
import copy
import json
import math
import os
import re
import tempfile
import uuid
from pathlib import Path

FIELDS = {'id', 'title', 'body', 'color', 'x', 'y', 'width', 'height',
          'visible', 'deadline', 'alert'}
COMMAND_FIELDS = {
    'create': {'title', 'body', 'color', 'minutes'},
    'update': {'id', 'title', 'body', 'color', 'minutes'},
    'delete': {'id'}, 'visibility': {'id', 'visible'},
    'visibility_all': {'visible'}, 'schedule': {'id', 'minutes'},
    'cancel': {'id'}, 'dismiss': {'id'}, 'snooze': {'id'},
    'geometry': {'id', 'x', 'y', 'width', 'height'},
}


def number(value, label, low, high):
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'{label} must be between {low} and {high}.')
    return value


def validate(note):
    if not isinstance(note, dict) or set(note) != FIELDS:
        raise ValueError('Invalid note fields.')
    try:
        if str(uuid.UUID(note['id'])) != note['id']:
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise ValueError('Invalid note ID.') from None
    for key, limit in [('title', 200), ('body', 100000)]:
        if (not isinstance(note[key], str) or len(note[key]) > limit or '\x00' in note[key]
                or any(0xD800 <= ord(char) <= 0xDFFF for char in note[key])):
            raise ValueError(f'{key.capitalize()} must be text, at most {limit} characters, without null characters.')
    if not isinstance(note['color'], str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', note['color']):
        raise ValueError('Color must be a six-digit hex color, such as #fff2a8.')
    for key in ('visible', 'alert'):
        if type(note[key]) is not bool:
            raise ValueError(f'{key.capitalize()} must be true or false.')
    for key, low, high in [('x', -100000, 100000), ('y', -100000, 100000),
                           ('width', 220, 10000), ('height', 160, 10000)]:
        if type(note[key]) is not int or not low <= note[key] <= high:
            raise ValueError(f'{key} must be an integer between {low} and {high}.')
    if note['deadline'] is not None:
        number(note['deadline'], 'Deadline', 0, 1e12)
    if note['alert'] and note['deadline'] is not None:
        raise ValueError('An active alert cannot also have a pending deadline.')


class Store:
    def __init__(self, directory: Path):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / 'notes.json'
        self.notes = []
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding='utf-8'))
                if (not isinstance(data, dict) or set(data) != {'version', 'notes'}
                        or type(data['version']) is not int or data['version'] != 1
                        or not isinstance(data['notes'], list)):
                    raise ValueError('Unsupported saved-data format.')
                for note in data['notes']:
                    validate(note)
                if len({note['id'] for note in data['notes']}) != len(data['notes']):
                    raise ValueError('Duplicate note IDs.')
                self.notes = data['notes']
            except (ValueError, UnicodeError) as error:
                raise ValueError(f'Cannot load {self.path}: {error} The file has been preserved.') from error

    def snapshot(self):
        return copy.deepcopy(self.notes)

    def _save(self, notes):
        name = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', suffix='.tmp',
                                             dir=self.directory, delete=False) as handle:
                name = handle.name
                json.dump({'version': 1, 'notes': notes}, handle, ensure_ascii=True, allow_nan=False)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(name, self.path)
        finally:
            if name and os.path.exists(name):
                os.unlink(name)

    def execute(self, command, payload, now):
        if not isinstance(command, str) or command not in COMMAND_FIELDS:
            raise ValueError('Unknown command.')
        if not isinstance(payload, dict) or set(payload) - COMMAND_FIELDS[command]:
            raise ValueError('Unexpected command fields.')
        number(now, 'Current time', 0, 1e12)
        notes = self.snapshot()
        if command == 'create':
            offset = (len(notes) % 12) * 24
            note = dict(id=str(uuid.uuid4()), title='', body='', color='#fff2a8',
                        x=80 + offset, y=80 + offset, width=300, height=260,
                        visible=True, deadline=None, alert=False)
            notes.append(note)
        elif command == 'visibility_all':
            note = None
        else:
            note = next((n for n in notes if n['id'] == payload.get('id')), None)
            if note is None:
                raise ValueError('Note not found. Refresh the editor and try again.')
        if command in ('create', 'update'):
            for key in ('title', 'body', 'color'):
                if key in payload:
                    note[key] = payload[key]
        if command == 'geometry':
            note.update({key: value for key, value in payload.items() if key != 'id'})
        if command == 'delete':
            notes.remove(note)
        if command in ('visibility', 'visibility_all'):
            if type(payload.get('visible')) is not bool:
                raise ValueError('Visible must be true or false.')
            for target in notes if command == 'visibility_all' else [note]:
                target['visible'] = payload['visible']
        if command == 'schedule' or (command in ('create', 'update') and 'minutes' in payload):
            minutes = payload.get('minutes')
            if minutes is None and command != 'schedule':
                note.update(deadline=None, alert=False)
            else:
                number(minutes, 'Reminder minutes', 1 / 60, 525600)
                note.update(deadline=now + minutes * 60, alert=False)
        if command in ('dismiss', 'cancel'):
            note.update(deadline=None, alert=False)
        if command == 'snooze':
            note.update(deadline=now + 300, alert=False)
        for target in notes:
            validate(target)
        self._save(notes)
        self.notes = notes
        return copy.deepcopy(note) if note is not None else {'ok': True}

    def tick(self, now):
        number(now, 'Current time', 0, 1e12)
        notes = self.snapshot()
        activated = []
        for note in notes:
            if note['deadline'] is not None and note['deadline'] <= now:
                note.update(deadline=None, alert=True, visible=True)
                activated.append(note['id'])
        if activated:
            self._save(notes)
            self.notes = notes
        return activated
