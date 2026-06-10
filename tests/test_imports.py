"""Smoke tests ensuring all modules and plugins import cleanly."""

import importlib

import pytest

MODULES = [
    "bot",
    "bot.bot",
    "bot.config",
    "bot.database",
    "bot.models",
    "bot.ffmpeg",
    "bot.ffmpeg.operations",
    "bot.ffmpeg.processor",
    "bot.ffmpeg.probe",
    "bot.helpers",
    "bot.keyboards",
    "bot.utils",
    "bot.utils.queue",
    "bot.utils.state",
    "bot.utils.ratelimit",
    "bot.handlers",
    "bot.handlers.processing",
    "bot.handlers.tools",
    "bot.plugins.commands",
    "bot.plugins.admin",
    "bot.plugins.video",
    "bot.plugins.callbacks",
    "bot.plugins.guards",
]


@pytest.mark.parametrize("module", MODULES)
def test_module_imports(module):
    assert importlib.import_module(module) is not None


def test_keyboards_build():
    from bot.keyboards import video_tools_keyboard, encode_codec_keyboard

    assert video_tools_keyboard().inline_keyboard
    assert encode_codec_keyboard().inline_keyboard


def test_language_keyboard_uses_namespace_and_skip():
    from bot.keyboards import language_keyboard

    markup = language_keyboard("lang_a")
    datas = [btn.callback_data for row in markup.inline_keyboard for btn in row]
    assert "lang_a|eng" in datas
    assert "lang_a|skip" in datas
    assert "menu|cancel" in datas
