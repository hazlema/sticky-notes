import os
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch
from sticky_notes.model import Store
from sticky_notes.desktop import PromptDialog, Desktop, clamp_geometry


@unittest.skipUnless(os.environ.get('DISPLAY'), 'An X11 display is required')
class DesktopTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = tk.Tk()
        self.root.withdraw()
        self.store = Store(Path(self.temp.name))
        self.desktop = Desktop(self.root, self.store, lambda note_id=None: None)
        self.addCleanup(self.cleanup)

    def cleanup(self):
        self.desktop.close()
        self.root.destroy()

    def test_window_visibility_content_and_deletion(self):
        note = self.store.execute('create', {'title': 'Hello', 'body': 'Paper', 'color': '#ccebd9'}, 100)
        self.desktop.refresh()
        self.root.update()
        view = self.desktop.windows[note['id']]
        self.assertEqual(view.body.get('1.0', 'end-1c'), 'Paper')
        self.assertEqual(view.body.cget('background'), '#ccebd9')
        self.assertTrue(view.edit_button.winfo_ismapped(), 'Edit must fit in default window')
        self.assertNotEqual(view.window.state(), 'withdrawn')
        self.store.execute('visibility', {'id': note['id'], 'visible': False}, 100)
        self.desktop.refresh()
        self.assertEqual(view.window.state(), 'withdrawn')
        self.store.execute('visibility', {'id': note['id'], 'visible': True}, 100)
        self.desktop.refresh()
        self.root.update()
        self.assertNotEqual(view.window.state(), 'withdrawn')
        self.store.execute('delete', {'id': note['id']}, 100)
        self.desktop.refresh()
        self.assertNotIn(note['id'], self.desktop.windows)

    def test_alert_reveal_and_bell_only_once(self):
        note = self.store.execute('create', {'minutes': 1}, 100)
        self.store.execute('visibility', {'id': note['id'], 'visible': False}, 100)
        self.desktop.refresh()
        with patch.object(self.root, 'bell') as bell:
            self.desktop.refresh(self.store.tick(160))
            self.desktop.refresh(self.store.tick(161))
            bell.assert_called_once()
        view = self.desktop.windows[note['id']]
        self.assertNotEqual(view.window.state(), 'withdrawn')
        self.assertEqual(view.window.cget('highlightbackground'), '#ce6522')
        self.root.update()
        self.assertTrue(view.dismiss_button.winfo_ismapped(), 'Dismiss must fit in default window')
        self.store.execute('dismiss', {'id': note['id']}, 162)
        self.desktop.refresh()
        self.assertNotEqual(view.window.cget('highlightbackground'), '#ce6522')

    def test_close_window_choices(self):
        for choice in ('cancel', 'hide', 'delete'):
            with self.subTest(choice=choice):
                note = self.store.execute('create', {'title': 'Close me'}, 100)
                self.desktop.refresh()
                self.root.update()
                view = self.desktop.windows[note['id']]
                with patch('sticky_notes.desktop.dialog') as dialog:
                    dialog.return_value = choice.title()
                    view.window.tk.call(view.window.protocol('WM_DELETE_WINDOW'))
                dialog.assert_called_once()
                saved = {n['id']: n for n in Store(Path(self.temp.name)).snapshot()}
                if choice == 'delete':
                    self.assertNotIn(note['id'], saved)
                    self.assertNotIn(note['id'], self.desktop.windows)
                else:
                    self.assertEqual(saved[note['id']]['visible'], choice == 'cancel')
                    self.assertEqual(view.window.state() == 'withdrawn', choice == 'hide')

    def test_delete_button_requires_confirmation(self):
        note = self.store.execute('create', {'title': 'Keep until confirmed'}, 100)
        self.desktop.refresh()
        self.root.update()
        view = self.desktop.windows[note['id']]
        self.assertTrue(view.delete_button.winfo_ismapped())
        with patch('sticky_notes.desktop.dialog', return_value='Cancel'):
            view.delete_button.invoke()
        self.assertIn(note['id'], self.desktop.windows)
        with patch('sticky_notes.desktop.dialog', return_value='Delete'):
            view.delete_button.invoke()
        self.assertNotIn(note['id'], self.desktop.windows)
        self.assertEqual(Store(Path(self.temp.name)).snapshot(), [])

    def test_real_close_dialog_buttons_and_window_dismissal(self):
        note = self.store.execute('create', {}, 100)
        self.desktop.refresh()
        self.root.update()
        parent = self.desktop.windows[note['id']].window
        for choice in ('Hide', 'Delete', 'Cancel', 'window-close'):
            labels = []

            def respond():
                dialog = next(child for child in parent.winfo_children()
                              if isinstance(child, PromptDialog))
                buttons = [button for frame in dialog.winfo_children()
                           for button in frame.winfo_children() if isinstance(button, tk.Button)]
                labels.extend(button.cget('text') for button in buttons)
                self.assertEqual(dialog.cget('background'), '#ccebd9')
                if choice == 'window-close':
                    dialog.tk.call(dialog.protocol('WM_DELETE_WINDOW'))
                else:
                    next(button for button in buttons if button.cget('text') == choice).invoke()

            self.root.after(30, respond)
            dialog = PromptDialog(parent, ['Hide', 'Delete', 'Cancel'], 'A dynamic prompt', color='#ccebd9')
            self.assertEqual(labels, ['Hide', 'Delete', 'Cancel'])
            self.assertEqual(dialog.result, None if choice == 'window-close' else choice)

    def test_long_title_keeps_hide_control_visible(self):
        note = self.store.execute('create', {'title': 'Long title ' * 18}, 100)
        self.desktop.refresh()
        self.root.update()
        view = self.desktop.windows[note['id']]
        self.assertTrue(view.hide_button.winfo_ismapped())

    def test_geometry_roundtrip(self):
        note = self.store.execute('create', {}, 100)
        self.desktop.refresh()
        self.root.update()
        view = self.desktop.windows[note['id']]
        view.window.geometry('410x310+25+35')
        self.root.update()
        self.desktop.close()
        loaded = Store(Path(self.temp.name)).snapshot()[0]
        self.assertEqual((loaded['width'], loaded['height'], loaded['x'], loaded['y']), (410, 310, 25, 35))


class GeometryTests(unittest.TestCase):
    def test_disconnected_screen_clamps_note(self):
        self.assertEqual(clamp_geometry(-5000, 3000, 300, 260, 1280, 720), (0, 460, 300, 260))
        self.assertEqual(clamp_geometry(0, 0, 4000, 3000, 1280, 720), (0, 0, 1280, 720))


if __name__ == '__main__':
    unittest.main()
