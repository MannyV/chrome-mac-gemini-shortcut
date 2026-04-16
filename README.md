# Chrome Gemini Push-to-Talk

A macOS background daemon that enables push-to-talk dictation directly into Google Chrome's Gemini side panel.

## How it works

Hold **Shift + Q** while Chrome is in focus:
1. Opens the Gemini side panel (`Ctrl+G`)
2. Clicks the Gemini input field
3. Clears the field and activates Onit dictation (via `Fn` key simulation)
4. On release, waits for Onit to transcribe your voice into the field
5. Auto-submits via `Enter` once text is confirmed — never submits an empty field

## Requirements

- macOS
- Google Chrome with Gemini side panel enabled
- [Onit](https://onit.ai) installed
- Python 3.9+

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Grant **Accessibility** and **Input Monitoring** permissions to the app in  
`System Settings → Privacy & Security`.

## Run

```bash
.venv/bin/python3 main.py
```

Or build a standalone app:

```bash
python3 setup.py py2app
```

Then move `dist/PushToTalk.app` to `/Applications` and add to **Login Items**.
