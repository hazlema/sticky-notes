"""Install the launcher and optional login autostart: python3 -m sticky_notes.install."""
import argparse
import os
from pathlib import Path
import sys


def desktop_value(value):
    return str(value).replace('\\', '\\\\').replace('\n', '\\n').replace('\r', '\\r')


def exec_argument(value):
    # Desktop Exec quoting is not shell quoting; percent signs are field codes.
    value = str(value).replace('%', '%%')
    value = ''.join('\\' + char if char in '\\"`$' else char for char in value)
    return desktop_value('"' + value + '"')


def desktop_entry(project, comment, exec_tail, extra_lines):
    return '\n'.join([
        '[Desktop Entry]', 'Version=1.0', 'Type=Application', 'Name=Sticky Notes',
        f'Comment={desktop_value(comment)}',
        f'Exec={exec_argument(sys.executable)} -m sticky_notes{exec_tail}',
        f'Path={desktop_value(project)}',
        f'Icon={desktop_value(project / "sticky_notes/icon.svg")}',
        'Terminal=false', 'StartupNotify=false', 'StartupWMClass=StickyNotes',
        *extra_lines, '',
    ])


def wants_autostart(args):
    if args.autostart:
        return True
    if args.no_autostart:
        return False
    if not sys.stdin.isatty():
        print('Skipped the login autostart entry; rerun with --autostart to enable it.')
        return False
    while True:
        try:
            answer = input('Start notes automatically at login? [Y/n] ').strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return False
        if answer in ('', 'y', 'yes'):
            return True
        if answer in ('n', 'no'):
            return False
        print('Please answer y or n.')


def main():
    parser = argparse.ArgumentParser(description='Install the Sticky Notes launcher and optional login autostart for this user.')
    parser.add_argument('--applications-dir', type=Path,
                        default=Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local/share') / 'applications')
    parser.add_argument('--autostart-dir', type=Path,
                        default=Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config') / 'autostart')
    autostart_flags = parser.add_mutually_exclusive_group()
    autostart_flags.add_argument('--autostart', action='store_true',
                                 help='install the login autostart entry without asking')
    autostart_flags.add_argument('--no-autostart', action='store_true',
                                 help='skip the login autostart entry without asking')
    args = parser.parse_args()
    project = Path(__file__).resolve().parent.parent
    entry = desktop_entry(project, 'Open your sticky note editor; notes keep running when the editor closes',
                          ' --editor', ['Categories=Utility;', 'Keywords=notes;sticky;reminders;'])
    directory = args.applications_dir.expanduser()
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / 'sticky-notes.desktop'
    target.write_text(entry, encoding='utf-8')
    print(f'Installed: {target}')
    print('Open Sticky Notes from your application menu. You can pin it to your launcher.')
    if wants_autostart(args):
        autostart = desktop_entry(project, 'Restore sticky notes at login', '',
                                  ['X-GNOME-Autostart-enabled=true'])
        directory = args.autostart_dir.expanduser()
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / 'sticky-notes.desktop'
        target.write_text(autostart, encoding='utf-8')
        print(f'Installed: {target}')
        print('Sticky notes will restore automatically at login.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
