from setuptools import setup

APP = ['main.py']
DATA_FILES = []
OPTIONS = {
    'argv_emulation': False,
    'plist': {
        'LSUIElement': True,  # Ensures it runs as a background app with no Dock icon
        'CFBundleName': 'PushToTalk',
        'CFBundleDisplayName': 'Push To Talk',
        'CFBundleIdentifier': 'com.emmanuelvayleux.PushToTalk',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        # Usually required if prompting for access natively:
        'NSAppleEventsUsageDescription': 'PushToTalk needs access to control Chrome.',
    },
    'packages': ['pynput', 'Quartz', 'AppKit'],
}

setup(
    app=APP,
    name='PushToTalk',
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
