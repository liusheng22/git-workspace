from __future__ import annotations

from textual import events
from textual.drivers.linux_driver import LinuxDriver

import git_workspace.terminal as terminal
from git_workspace.terminal import (
    KEYBOARD_PROTOCOL_ENABLE,
    SELECTION_HOSTILE_RESET,
    SHIFT_ENTER_COMPAT_WINDOW_SECONDS,
    SelectionFriendlyLinuxDriver,
    is_selection_hostile_key,
    printable_character_for_key,
    strip_selection_hostile_modes,
)


def test_strip_selection_hostile_modes_filters_focus_and_kitty_keyboard() -> None:
    assert strip_selection_hostile_modes("before\x1b[?1004h\x1b[>25uafter") == "beforeafter"
    assert strip_selection_hostile_modes("before\x1b[>1uafter") == "before\x1b[>1uafter"
    assert strip_selection_hostile_modes("before\x1b[>9uafter") == "beforeafter"
    assert strip_selection_hostile_modes("before\x1b[?1000h\x1b[?1003h\x1b[?1006hafter") == "beforeafter"


def test_selection_friendly_driver_filters_selection_hostile_modes(monkeypatch) -> None:
    written: list[str] = []

    monkeypatch.setattr(LinuxDriver, "write", lambda self, data: written.append(data))

    driver = object.__new__(SelectionFriendlyLinuxDriver)
    driver.write("before\x1b[?1004h\x1b[>25u\x1b[>1uafter")

    assert written == ["before\x1b[>1uafter"]


def test_selection_friendly_driver_skips_empty_filtered_write(monkeypatch) -> None:
    written: list[str] = []

    monkeypatch.setattr(LinuxDriver, "write", lambda self, data: written.append(data))

    driver = object.__new__(SelectionFriendlyLinuxDriver)
    driver.write("\x1b[?1004h\x1b[>25u")

    assert written == []


def test_selection_friendly_driver_resets_stale_terminal_modes(monkeypatch) -> None:
    written: list[str] = []
    flushed: list[bool] = []

    monkeypatch.setattr(LinuxDriver, "write", lambda self, data: written.append(data))
    monkeypatch.setattr(LinuxDriver, "flush", lambda self: flushed.append(True))

    driver = object.__new__(SelectionFriendlyLinuxDriver)
    driver.disable_selection_hostile_modes()

    assert written == [SELECTION_HOSTILE_RESET]
    assert flushed == [True]


def test_selection_friendly_driver_enables_keyboard_protocol(monkeypatch) -> None:
    written: list[str] = []
    flushed: list[bool] = []

    monkeypatch.setattr(LinuxDriver, "write", lambda self, data: written.append(data))
    monkeypatch.setattr(LinuxDriver, "flush", lambda self: flushed.append(True))

    driver = object.__new__(SelectionFriendlyLinuxDriver)
    driver.enable_keyboard_protocol()

    assert written == [KEYBOARD_PROTOCOL_ENABLE]
    assert flushed == [True]


def test_selection_hostile_keys_are_filtered() -> None:
    assert is_selection_hostile_key("left_super")
    assert is_selection_hostile_key("super+c")
    assert is_selection_hostile_key("meta+enter")
    assert not is_selection_hostile_key("shift+enter")
    assert not is_selection_hostile_key("ctrl+c")


def test_printable_character_for_modified_key_protocol() -> None:
    assert printable_character_for_key("space") == " "
    assert printable_character_for_key("minus") == "-"
    assert printable_character_for_key("slash") == "/"
    assert printable_character_for_key("shift+slash") == "/"
    assert printable_character_for_key("ctrl+slash") is None


def test_selection_friendly_driver_drops_super_key_events(monkeypatch) -> None:
    processed: list[events.Key] = []

    monkeypatch.setattr(LinuxDriver, "process_message", lambda self, message: processed.append(message))

    driver = object.__new__(SelectionFriendlyLinuxDriver)
    driver.process_message(events.Key("left_super", None))
    driver.process_message(events.Key("super+c", None))
    driver.process_message(events.Key("shift+enter", None))

    assert [event.key for event in processed] == ["shift+enter"]


def test_selection_friendly_driver_does_not_record_keys_when_debug_is_off() -> None:
    recorded: list[tuple[str, object]] = []

    class App:
        key_debug_enabled = False

        def call_from_thread(self, callback, *args):
            callback(*args)

        def record_raw_input(self, raw_data: bytes, decoded_data: str) -> None:
            recorded.append(("raw", (raw_data, decoded_data)))

        def record_key_event(
            self,
            key: str,
            character: str | None,
            normalized_character: str | None,
            dropped: bool,
        ) -> None:
            recorded.append(("key", (key, character, normalized_character, dropped)))

    driver = object.__new__(SelectionFriendlyLinuxDriver)
    driver._app = App()

    driver.record_raw_input(b"x", "x")
    driver.record_key_event("left_super", None, None, True)

    assert recorded == []


def test_selection_friendly_driver_records_safe_keys_when_debug_is_on() -> None:
    recorded: list[tuple[str, object]] = []

    class App:
        key_debug_enabled = True

        def call_from_thread(self, callback, *args):
            callback(*args)

        def record_raw_input(self, raw_data: bytes, decoded_data: str) -> None:
            recorded.append(("raw", (raw_data, decoded_data)))

        def record_key_event(
            self,
            key: str,
            character: str | None,
            normalized_character: str | None,
            dropped: bool,
        ) -> None:
            recorded.append(("key", (key, character, normalized_character, dropped)))

    driver = object.__new__(SelectionFriendlyLinuxDriver)
    driver._app = App()

    driver.record_raw_input(b"x", "x")
    driver.record_key_event("a", "a", None, False)

    assert recorded == [("raw", (b"x", "x")), ("key", ("a", "a", None, False))]


def test_selection_friendly_driver_does_not_record_hostile_key_event_when_debug_is_on() -> None:
    recorded: list[tuple[str, object]] = []

    class App:
        key_debug_enabled = True

        def call_from_thread(self, callback, *args):
            callback(*args)

        def record_key_event(
            self,
            key: str,
            character: str | None,
            normalized_character: str | None,
            dropped: bool,
        ) -> None:
            recorded.append(("key", (key, character, normalized_character, dropped)))

    driver = object.__new__(SelectionFriendlyLinuxDriver)
    driver._app = App()

    driver.record_key_event("left_super", None, None, True)

    assert recorded == []


def test_selection_friendly_driver_does_not_record_super_key_input_when_debug_is_on() -> None:
    recorded: list[tuple[str, object]] = []

    class App:
        key_debug_enabled = True

        def call_from_thread(self, callback, *args):
            callback(*args)

        def record_raw_input(self, raw_data: bytes, decoded_data: str) -> None:
            recorded.append(("raw", (raw_data, decoded_data)))

        def record_key_event(
            self,
            key: str,
            character: str | None,
            normalized_character: str | None,
            dropped: bool,
        ) -> None:
            recorded.append(("key", (key, character, normalized_character, dropped)))

    driver = object.__new__(SelectionFriendlyLinuxDriver)
    driver._app = App()

    driver.record_key_input(b"\x1b[57444;9u", "\x1b[57444;9u", "left_super", None, None, True)

    assert recorded == []


def test_selection_friendly_driver_records_non_hostile_key_input_when_debug_is_on() -> None:
    recorded: list[tuple[str, object]] = []

    class App:
        key_debug_enabled = True

        def call_from_thread(self, callback, *args):
            callback(*args)

        def record_raw_input(self, raw_data: bytes, decoded_data: str) -> None:
            recorded.append(("raw", (raw_data, decoded_data)))

        def record_key_event(
            self,
            key: str,
            character: str | None,
            normalized_character: str | None,
            dropped: bool,
        ) -> None:
            recorded.append(("key", (key, character, normalized_character, dropped)))

    driver = object.__new__(SelectionFriendlyLinuxDriver)
    driver._app = App()

    driver.record_key_input(b"a", "a", "a", "a", None, False)

    assert recorded == [("raw", (b"a", "a")), ("key", ("a", "a", None, False))]


def test_selection_friendly_driver_restores_printable_key_characters(monkeypatch) -> None:
    processed: list[events.Key] = []

    monkeypatch.setattr(LinuxDriver, "process_message", lambda self, message: processed.append(message))

    driver = object.__new__(SelectionFriendlyLinuxDriver)
    driver.process_message(events.Key("space", None))
    driver.process_message(events.Key("minus", None))
    driver.process_message(events.Key("slash", None))
    driver.process_message(events.Key("ctrl+slash", None))

    assert [(event.key, event.character) for event in processed] == [
        ("space", " "),
        ("minus", "-"),
        ("slash", "/"),
        ("ctrl+slash", None),
    ]


def test_selection_friendly_driver_promotes_enter_after_left_shift(monkeypatch) -> None:
    processed: list[events.Key] = []
    times = iter([10.0, 10.2])

    monkeypatch.setattr(terminal.time, "monotonic", lambda: next(times))
    monkeypatch.setattr(LinuxDriver, "process_message", lambda self, message: processed.append(message))

    driver = object.__new__(SelectionFriendlyLinuxDriver)
    driver.process_message(events.Key("left_shift", None))
    driver.process_message(events.Key("enter", "\r"))

    assert [(event.key, event.character) for event in processed] == [("shift+enter", None)]


def test_selection_friendly_driver_promotes_enter_after_right_shift(monkeypatch) -> None:
    processed: list[events.Key] = []
    times = iter([10.0, 10.2])

    monkeypatch.setattr(terminal.time, "monotonic", lambda: next(times))
    monkeypatch.setattr(LinuxDriver, "process_message", lambda self, message: processed.append(message))

    driver = object.__new__(SelectionFriendlyLinuxDriver)
    driver.process_message(events.Key("right_shift", None))
    driver.process_message(events.Key("enter", "\r"))

    assert [(event.key, event.character) for event in processed] == [("shift+enter", None)]


def test_selection_friendly_driver_does_not_promote_stale_shift(monkeypatch) -> None:
    processed: list[events.Key] = []
    times = iter([10.0, 10.0 + SHIFT_ENTER_COMPAT_WINDOW_SECONDS + 0.1])

    monkeypatch.setattr(terminal.time, "monotonic", lambda: next(times))
    monkeypatch.setattr(LinuxDriver, "process_message", lambda self, message: processed.append(message))

    driver = object.__new__(SelectionFriendlyLinuxDriver)
    driver.process_message(events.Key("left_shift", None))
    driver.process_message(events.Key("enter", "\r"))

    assert [(event.key, event.character) for event in processed] == [("enter", "\r")]


def test_selection_friendly_driver_clears_shift_compat_on_other_key(monkeypatch) -> None:
    processed: list[events.Key] = []
    times = iter([10.0, 10.1, 10.2])

    monkeypatch.setattr(terminal.time, "monotonic", lambda: next(times))
    monkeypatch.setattr(LinuxDriver, "process_message", lambda self, message: processed.append(message))

    driver = object.__new__(SelectionFriendlyLinuxDriver)
    driver.process_message(events.Key("left_shift", None))
    driver.process_message(events.Key("a", "a"))
    driver.process_message(events.Key("enter", "\r"))

    assert [(event.key, event.character) for event in processed] == [("a", "a"), ("enter", "\r")]
