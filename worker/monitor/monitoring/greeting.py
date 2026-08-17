"""Compatibility wrapper for controllers that still send ``greeting``."""

from monitor.monitoring.chat import handle_chat


def handle_greeting(msg, reporter, stop_event=None, main_loop=None):
    return handle_chat(
        msg,
        reporter,
        stop_event=stop_event,
        main_loop=main_loop,
    )
