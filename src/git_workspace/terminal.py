from __future__ import annotations

import re
import selectors
import time
from codecs import getincrementaldecoder
from contextlib import suppress

from textual import events
from textual._loop import loop_last
from textual._parser import ParseError
from textual._xterm_parser import XTermParser
from textual.drivers.linux_driver import LinuxDriver
from textual.message import Message

KITTY_KEYBOARD = "\x1b[>1u"
XTERM_MODIFY_OTHER_KEYS = "\x1b[>4;2m"
KEYBOARD_PROTOCOL_ENABLE = f"{XTERM_MODIFY_OTHER_KEYS}{KITTY_KEYBOARD}"
SAFE_KITTY_KEYBOARD_ENABLES = {KITTY_KEYBOARD}
UNSAFE_KITTY_KEYBOARD_ENABLE_RE = re.compile(r"\x1b\[>[0-9;]*u")
SHIFT_ENTER_COMPAT_WINDOW_SECONDS = 1.25
STANDALONE_SHIFT_KEYS = {"left_shift", "right_shift"}
ENTER_KEYS = {"enter", "\r", "\n"}
MODIFIER_ONLY_KEYS = {
    "left_shift",
    "right_shift",
    "left_control",
    "right_control",
    "left_alt",
    "right_alt",
    "left_super",
    "right_super",
    "left_hyper",
    "right_hyper",
    "left_meta",
    "right_meta",
    "iso_level3_shift",
    "iso_level5_shift",
}
PRINTABLE_KEY_CHARACTERS = {
    "space": " ",
    "exclamation_mark": "!",
    "quotation_mark": '"',
    "number_sign": "#",
    "dollar_sign": "$",
    "percent_sign": "%",
    "ampersand": "&",
    "apostrophe": "'",
    "left_parenthesis": "(",
    "right_parenthesis": ")",
    "asterisk": "*",
    "plus": "+",
    "comma": ",",
    "minus": "-",
    "full_stop": ".",
    "slash": "/",
    "colon": ":",
    "semicolon": ";",
    "less_than_sign": "<",
    "equals_sign": "=",
    "greater_than_sign": ">",
    "question_mark": "?",
    "at": "@",
    "left_square_bracket": "[",
    "backslash": "\\",
    "right_square_bracket": "]",
    "circumflex_accent": "^",
    "underscore": "_",
    "grave_accent": "`",
    "left_curly_bracket": "{",
    "vertical_line": "|",
    "right_curly_bracket": "}",
    "tilde": "~",
}
SELECTION_HOSTILE_ENABLES = (
    "\x1b[?1000h",  # VT200 mouse reporting
    "\x1b[?1002h",  # button-event mouse reporting
    "\x1b[?1003h",  # any-event mouse reporting
    "\x1b[?1005h",  # UTF-8 mouse coordinates
    "\x1b[?1006h",  # SGR mouse coordinates
    "\x1b[?1015h",  # urxvt mouse coordinates
    "\x1b[?1016h",  # pixel-position mouse reporting
    "\x1b[?1004h",  # FocusIn/FocusOut reporting
)

SELECTION_HOSTILE_RESET = "".join(
    [
        "\x1b[?1000l",  # VT200 mouse reporting
        "\x1b[?1002l",  # button-event mouse reporting
        "\x1b[?1003l",  # any-event mouse reporting
        "\x1b[?1005l",  # UTF-8 mouse coordinates
        "\x1b[?1006l",  # SGR mouse coordinates
        "\x1b[?1015l",  # urxvt mouse coordinates
        "\x1b[?1016l",  # pixel-position mouse reporting
        "\x1b[?1004l",  # FocusIn/FocusOut reporting
        "\x1b[>4;0m",  # xterm modifyOtherKeys
        "\x1b[<u",  # kitty keyboard protocol
    ]
)


def strip_selection_hostile_modes(data: str) -> str:
    for sequence in SELECTION_HOSTILE_ENABLES:
        data = data.replace(sequence, "")
    return UNSAFE_KITTY_KEYBOARD_ENABLE_RE.sub(
        lambda match: match.group(0) if match.group(0) in SAFE_KITTY_KEYBOARD_ENABLES else "",
        data,
    )


def is_selection_hostile_key(key: str) -> bool:
    if key in MODIFIER_ONLY_KEYS:
        return True
    return any(part in {"super", "hyper", "meta"} for part in key.split("+"))


def is_recent_standalone_shift(timestamp: float | None, now: float) -> bool:
    return timestamp is not None and 0 <= now - timestamp <= SHIFT_ENTER_COMPAT_WINDOW_SECONDS


def printable_character_for_key(key: str) -> str | None:
    parts = key.split("+")
    if any(part not in {"shift", parts[-1]} for part in parts[:-1]):
        return None
    return PRINTABLE_KEY_CHARACTERS.get(parts[-1])


class SelectionFriendlyLinuxDriver(LinuxDriver):
    """Linux/macOS terminal driver that leaves native text selection alone."""

    def start_application_mode(self) -> None:
        super().start_application_mode()
        self.disable_selection_hostile_modes()
        self.enable_keyboard_protocol()

    def disable_selection_hostile_modes(self) -> None:
        self.write(SELECTION_HOSTILE_RESET)
        self.flush()

    def enable_keyboard_protocol(self) -> None:
        self.write(KEYBOARD_PROTOCOL_ENABLE)
        self.flush()

    def record_raw_input(self, raw_data: bytes, decoded_data: str) -> None:
        app = getattr(self, "_app", None)
        if not getattr(app, "key_debug_enabled", False):
            return
        recorder = getattr(app, "record_raw_input", None)
        if recorder is None:
            return
        with suppress(RuntimeError):
            app.call_from_thread(recorder, raw_data, decoded_data)

    def record_key_input(
        self,
        raw_data: bytes | None,
        decoded_data: str | None,
        key: str,
        character: str | None,
        normalized_character: str | None,
        dropped: bool,
    ) -> None:
        if is_selection_hostile_key(key):
            return
        if raw_data is not None and decoded_data is not None:
            self.record_raw_input(raw_data, decoded_data)
        self.record_key_event(key, character, normalized_character, dropped)

    def record_key_event(
        self,
        key: str,
        character: str | None,
        normalized_character: str | None,
        dropped: bool,
    ) -> None:
        if is_selection_hostile_key(key):
            return
        app = getattr(self, "_app", None)
        if not getattr(app, "key_debug_enabled", False):
            return
        recorder = getattr(app, "record_key_event", None)
        if recorder is None:
            return
        with suppress(RuntimeError):
            app.call_from_thread(recorder, key, character, normalized_character, dropped)

    def promote_enter_after_standalone_shift(self, message: events.Key, now: float) -> events.Key | None:
        if message.key not in ENTER_KEYS:
            return None
        if not is_recent_standalone_shift(getattr(self, "_last_standalone_shift_at", None), now):
            return None
        self._last_standalone_shift_at = None
        return events.Key("shift+enter", None)

    def process_message(self, message: Message) -> None:
        if isinstance(message, events.Key):
            now = time.monotonic()
            raw_data = getattr(message, "_gws_raw_data", None)
            decoded_data = getattr(message, "_gws_decoded_data", None)

            if message.key in STANDALONE_SHIFT_KEYS:
                self._last_standalone_shift_at = now
                self.record_key_input(raw_data, decoded_data, message.key, message.character, None, True)
                return

            promoted = self.promote_enter_after_standalone_shift(message, now)
            if promoted is not None:
                self.record_key_input(raw_data, decoded_data, promoted.key, promoted.character, None, False)
                super().process_message(promoted)
                return

            self._last_standalone_shift_at = None
            dropped = is_selection_hostile_key(message.key)
            normalized_character = None
            if message.character is None:
                normalized_character = printable_character_for_key(message.key)
            self.record_key_input(
                raw_data,
                decoded_data,
                message.key,
                message.character,
                normalized_character,
                dropped,
            )
            if dropped:
                return
            if normalized_character is not None:
                message = events.Key(message.key, normalized_character)
        super().process_message(message)

    def write(self, data: str) -> None:
        data = strip_selection_hostile_modes(data)
        if data:
            super().write(data)

    def run_input_thread(self) -> None:
        selector = selectors.SelectSelector()
        selector.register(self.fileno, selectors.EVENT_READ)

        fileno = self.fileno
        event_read = selectors.EVENT_READ

        parser = XTermParser(self._debug)
        feed = parser.feed
        tick = parser.tick

        decode = getincrementaldecoder("utf-8")().decode
        read = __import__("os").read

        def process_selector_events(
            selector_events: list[tuple[selectors.SelectorKey, int]],
            final: bool = False,
        ) -> None:
            for last, (_selector_key, mask) in loop_last(selector_events):
                if mask & event_read:
                    raw_data = read(fileno, 1024 * 4)
                    unicode_data = decode(raw_data, final=final and last)
                    if not unicode_data:
                        break
                    for event in feed(unicode_data):
                        event._gws_raw_data = raw_data
                        event._gws_decoded_data = unicode_data
                        self.process_message(event)
            for event in tick():
                self.process_message(event)

        try:
            while not self.exit_event.is_set():
                process_selector_events(selector.select(0.1))
            selector.unregister(self.fileno)
            process_selector_events(selector.select(0.1), final=True)
        finally:
            selector.close()
            try:
                for _event in feed(""):
                    pass
            except (EOFError, ParseError):
                pass
