import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from sticky_notes.model import Store


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.store = Store(self.directory)

    def create(self, **values):
        return self.store.execute('create', values, 100)

    def command(self, command, note, **values):
        return self.store.execute(command, {'id': note['id'], **values}, 100)

    def test_persist_edit_geometry_and_delete(self):
        note = self.create(title='Tea', body='Take a break', color='#fff2a8')
        self.command('update', note, body='Changed')
        self.command('geometry', note, x=20, y=30, width=400, height=300)
        loaded = Store(self.directory).snapshot()[0]
        self.assertEqual((loaded['body'], loaded['width'], loaded['x']), ('Changed', 400, 20))
        self.command('delete', note)
        self.assertEqual(Store(self.directory).snapshot(), [])

    def test_reminder_reveals_hidden_note_once_and_survives_restart(self):
        note = self.create()
        self.command('schedule', note, minutes=1)
        self.command('visibility', note, visible=False)
        self.assertEqual(self.store.tick(159), [])
        self.assertEqual(self.store.tick(160), [note['id']])
        self.assertTrue(self.store.snapshot()[0]['visible'])
        self.assertTrue(self.store.snapshot()[0]['alert'])
        self.assertEqual(Store(self.directory).tick(161), [])
        self.command('visibility', note, visible=False)
        self.assertEqual(self.store.tick(170), [])
        self.assertFalse(self.store.snapshot()[0]['visible'])

    def test_overdue_snooze_dismiss_cancel(self):
        note = self.create()
        self.command('schedule', note, minutes=1)
        self.store = Store(self.directory)
        self.assertEqual(self.store.tick(500), [note['id']])
        self.command('snooze', note)
        self.assertEqual(self.store.snapshot()[0]['deadline'], 400)
        self.assertFalse(self.store.snapshot()[0]['alert'])
        self.assertEqual(self.store.tick(400), [note['id']])
        self.command('dismiss', note)
        self.assertFalse(Store(self.directory).snapshot()[0]['alert'])
        self.command('schedule', note, minutes=1)
        self.command('cancel', note)
        self.assertEqual(self.store.tick(999), [])

    def test_visibility_all_and_snapshot_is_copy(self):
        self.create()
        self.create()
        self.store.execute('visibility_all', {'visible': False}, 100)
        self.assertFalse(any(n['visible'] for n in self.store.snapshot()))
        self.store.execute('visibility_all', {'visible': True}, 100)
        snapshot = self.store.snapshot()
        snapshot[0]['title'] = 'mutated'
        self.assertNotEqual(self.store.snapshot()[0]['title'], 'mutated')
        self.assertTrue(all(n['visible'] for n in self.store.snapshot()))

    def test_invalid_input_leaves_state_unchanged(self):
        note = self.create()
        for command, payload in [
            ('create', {'color': 'red'}), ('create', {'title': 'x' * 201}),
            ('create', {'body': 'x' * 100001}), ('create', {'bogus': 1}), ('create', {'body': '\ud800'}),
            ('visibility', {'id': note['id'], 'visible': 1}),
            ('schedule', {'id': note['id'], 'minutes': float('nan')}),
            ('schedule', {'id': note['id'], 'minutes': float('inf')}),
            ('schedule', {'id': note['id'], 'minutes': 0}),
            ('schedule', {'id': note['id'], 'minutes': True}),
            ('geometry', {'id': note['id'], 'width': -1}),
            ('delete', {'id': 'missing'}), ('bogus', {})
        ]:
            before = self.store.snapshot()
            with self.subTest(command=command, payload=payload):
                with self.assertRaises(ValueError):
                    self.store.execute(command, payload, 100)
                self.assertEqual(self.store.snapshot(), before)

    def test_atomic_save_failure_preserves_file_and_memory(self):
        note = self.create(title='Original')
        old_bytes = (self.directory / 'notes.json').read_bytes()
        with patch('sticky_notes.model.os.replace', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                self.command('update', note, title='Lost')
        self.assertEqual((self.directory / 'notes.json').read_bytes(), old_bytes)
        self.assertEqual(self.store.snapshot()[0]['title'], 'Original')
        self.assertEqual(list(self.directory.glob('*.tmp')), [])

    def test_corrupt_store_not_overwritten(self):
        path = self.directory / 'notes.json'
        for content in ['not json', '{"version": 99, "notes": []}',
                        '{"version": 1, "notes": [{}]}']:
            path.write_text(content)
            with self.assertRaises(ValueError):
                Store(self.directory)
            self.assertEqual(path.read_text(), content)

    def test_create_with_timer_is_one_atomic_operation(self):
        note = self.create(minutes=2)
        self.assertEqual(note['deadline'], 220)
        self.assertEqual(self.store.tick(220), [note['id']])


if __name__ == '__main__':
    unittest.main()
