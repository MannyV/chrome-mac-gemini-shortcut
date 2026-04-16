#!/usr/bin/env python3
"""
macOS Push-to-Talk Dictation Daemon

Listens for the user holding Shift + Q. When triggered in Google Chrome,
it opens the Ask Gemini side panel (Ctrl+G) and simulates holding the
Fn key to activate Onit dictation. Releasing either key ends the session.

Requirements:
    - macOS with Accessibility permissions granted to the terminal / IDE.
    - Google Chrome as the target browser.
    - pynput, pyobjc
"""

import threading
import time

VERSION = "1.0.0"

from pynput import keyboard
import subprocess
import Quartz
from Quartz.CoreGraphics import (
    CGEventCreateKeyboardEvent,
    CGEventCreateMouseEvent,
    CGEventPost,
    CGEventSetType,
    CGEventSetFlags,
    kCGHIDEventTap,
    kCGEventFlagsChanged,
    kCGEventFlagMaskControl,
    kCGEventFlagMaskShift,
    kCGEventFlagMaskCommand,
    kCGEventLeftMouseDown,
    kCGEventLeftMouseUp,
    kCGMouseButtonLeft,
)
from AppKit import NSWorkspace, NSPasteboard, NSStringPboardType


# ── Virtual Key Codes (Inside Macintosh, Events.h) ────────────────
FN_KEY_CODE   = 63   # kVK_Function
CTRL_KEY_CODE = 59   # kVK_Control (Left)
G_KEY_CODE    = 5    # kVK_ANSI_G
Q_KEY_CODE    = 12   # kVK_ANSI_Q
TAB_KEY_CODE  = 48   # kVK_Tab
BACKSPACE_KEY_CODE = 51 # kVK_Delete
RETURN_KEY_CODE = 36  # kVK_Return
A_KEY_CODE    = 0    # kVK_ANSI_A
C_KEY_CODE    = 8    # kVK_ANSI_C

# ── Event Flags ───────────────────────────────────────────────────
FN_FLAG = 0x800000   # NX_SECONDARYFNMASK / kCGEventFlagMaskSecondaryFn

# ── State Variables ───────────────────────────────────
shift_pressed  = False
q_pressed      = False
is_recording   = False
_cached_click  = None   # (x, y) cached from last osascript call


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Helpers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def is_chrome_active() -> bool:
    """Return True only when Google Chrome is the frontmost application."""
    app = NSWorkspace.sharedWorkspace().frontmostApplication()
    return app.localizedName() == "Google Chrome"


def _is_shift(key) -> bool:
    """Identify a Shift key event."""
    return key in (keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r)


def _is_q(key) -> bool:
    """Identify a Q key event by vk code or character."""
    if hasattr(key, "vk") and key.vk == Q_KEY_CODE:
        return True
    try:
        return key.char in ("q", "Q")
    except AttributeError:
        return False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Quartz CoreGraphics – Keystroke Simulation
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _post_key(code: int, down: bool, flags: int = 0):
    """Post a standard keyDown / keyUp event."""
    event = CGEventCreateKeyboardEvent(None, code, down)
    if flags:
        CGEventSetFlags(event, flags)
    CGEventPost(kCGHIDEventTap, event)


def _post_fn(down: bool):
    """Post an Fn (flagsChanged) event with the correct flag mask."""
    event = CGEventCreateKeyboardEvent(None, FN_KEY_CODE, down)
    CGEventSetType(event, kCGEventFlagsChanged)
    CGEventSetFlags(event, FN_FLAG if down else 0)
    CGEventPost(kCGHIDEventTap, event)


def _send_ctrl_g():
    """Simulate Ctrl+G → opens the Ask Gemini side panel in Chrome."""
    _post_key(CTRL_KEY_CODE, True)                          # Ctrl ↓
    _post_key(G_KEY_CODE, True, flags=kCGEventFlagMaskControl)  # G ↓
    _post_key(G_KEY_CODE, False)                            # G ↑
    _post_key(CTRL_KEY_CODE, False)                         # Ctrl ↑


def _click_gemini_input():
    """Click the Gemini input. Uses cached coords to avoid slow osascript every press."""
    global _cached_click
    if _cached_click is None:
        result = subprocess.run(["osascript", "-e", """
            tell application "System Events"
                tell process "Google Chrome"
                    set w to front window
                    set p to position of w
                    set s to size of w
                    set x1 to item 1 of p
                    set y1 to item 2 of p
                    set x2 to x1 + (item 1 of s)
                    set y2 to y1 + (item 2 of s)
                    return (x1 as string) & "," & (y1 as string) & "," & (x2 as string) & "," & (y2 as string)
                end tell
            end tell
        """], capture_output=True, text=True)
        raw = result.stdout.strip()
        try:
            x1, y1, x2, y2 = [int(p.strip()) for p in raw.split(",")]
            _cached_click = (x2 - 160, y2 - 60)
            print(f"   ✓ Cached click coords: {_cached_click}")
        except Exception as e:
            print(f"   ! Could not get Chrome bounds: {e}")
            return
    click_x, click_y = _cached_click
    pos = Quartz.CGPoint(click_x, click_y)
    dn = CGEventCreateMouseEvent(None, kCGEventLeftMouseDown, pos, kCGMouseButtonLeft)
    up = CGEventCreateMouseEvent(None, kCGEventLeftMouseUp,   pos, kCGMouseButtonLeft)
    CGEventPost(kCGHIDEventTap, dn)
    time.sleep(0.05)
    CGEventPost(kCGHIDEventTap, up)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Action Payloads
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _start_recording():
    """
    Open Gemini panel, click input, clear field, then start Onit as fast as possible.
    """
    _send_ctrl_g()
    time.sleep(0.25)        # minimal wait for panel to render
    _click_gemini_input()
    time.sleep(0.1)         # let click settle

    # Clear the field (Cmd+A → Delete) so we know it's empty — much faster than reading it
    _post_key(A_KEY_CODE, True, flags=kCGEventFlagMaskCommand)
    _post_key(A_KEY_CODE, False)
    time.sleep(0.04)
    _post_key(BACKSPACE_KEY_CODE, True)
    _post_key(BACKSPACE_KEY_CODE, False)
    time.sleep(0.04)

    # Start Onit – field is now empty and focused
    _post_fn(down=True)
    print("   ● Recording started  (Fn held)")


def _read_gemini_field_text():
    """Cmd+A / Cmd+C the focused Gemini field and return its text."""
    pb = NSPasteboard.generalPasteboard()
    saved = pb.stringForType_(NSStringPboardType)
    _post_key(A_KEY_CODE, True, flags=kCGEventFlagMaskCommand)
    _post_key(A_KEY_CODE, False)
    time.sleep(0.05)
    _post_key(C_KEY_CODE, True, flags=kCGEventFlagMaskCommand)
    _post_key(C_KEY_CODE, False)
    time.sleep(0.1)
    text = (pb.stringForType_(NSStringPboardType) or "").strip()
    if saved and saved != text:
        pb.clearContents()
        pb.setString_forType_(saved, NSStringPboardType)
    return text


def _stop_recording():
    """Release Fn, poll until any text appears in the field, then press Enter."""
    _post_fn(down=False)
    print("   ○ Recording stopped  (Fn released)")

    # Wait for Onit to begin committing transcription
    time.sleep(0.8)

    deadline = time.time() + 8.0
    while time.time() < deadline:
        text = _read_gemini_field_text()
        print(f"   … field has {len(text)} chars")
        if text:
            print(f"   → Text confirmed ({len(text)} chars) — pressing Enter")
            _post_key(RETURN_KEY_CODE, True)
            _post_key(RETURN_KEY_CODE, False)
            return
        time.sleep(0.5)

    print("   → Field empty after 8s — NOT submitting")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  pynput Listener Callbacks
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def on_press(key):
    """Track Shift and Q key-down events and trigger the macro."""
    global shift_pressed, q_pressed, is_recording

    if _is_shift(key):
        shift_pressed = True
    elif _is_q(key):
        q_pressed = True

    # ── Trigger condition: both keys held, not already recording ──
    if shift_pressed and q_pressed and not is_recording:
        if not is_chrome_active():
            return
        is_recording = True
        # Spawn in a daemon thread so the listener is never blocked.
        threading.Thread(target=_start_recording, daemon=True).start()


def on_release(key):
    """Track Shift and Q key-up events and release the virtual Fn hold."""
    global shift_pressed, q_pressed, is_recording

    if _is_shift(key):
        shift_pressed = False
    elif _is_q(key):
        q_pressed = False

    # ── End condition: either trigger key released while recording ──
    if is_recording and (not shift_pressed or not q_pressed):
        _stop_recording()
        is_recording = False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Entry Point
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def main():
    print(f"🎙  Push-to-Talk v{VERSION} started")
    print("   Hold  Shift + Q  in Google Chrome to activate Onit dictation.")
    print("   Press Ctrl+C to quit.\n")

    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        listener.join()


if __name__ == "__main__":
    main()
