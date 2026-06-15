"""Smoke tests for the LoL Notifier skeleton."""

from __future__ import annotations

import asyncio
import unittest
from pathlib import Path


_SRC_ROOT = Path(__file__).resolve().parent.parent / "src"
_SCHEDULER_SRC = _SRC_ROOT / "astrbot_plugin_lol_notifier" / "scheduler.py"
_API_SRC = _SRC_ROOT / "astrbot_plugin_lol_notifier" / "api.py"
_FORMATTER_SRC = _SRC_ROOT / "astrbot_plugin_lol_notifier" / "formatter.py"
_MAIN_SRC = Path(__file__).resolve().parent.parent / "main.py"


class TestMainSurface(unittest.TestCase):
    def test_lol_command_group_exists(self):
        source = _MAIN_SRC.read_text(encoding="utf-8")
        self.assertIn('command_group("lol")', source)

    def test_lol_commands_exist(self):
        source = _MAIN_SRC.read_text(encoding="utf-8")
        for marker in ["lol_schedule", "lol_result", "lol_bp", "lol_detail", "lol_standings"]:
            self.assertIn(marker, source)


class TestLoLApiSkeleton(unittest.TestCase):
    def _import_api(self):
        import importlib.util
        import sys

        mod_name = "src.astrbot_plugin_lol_notifier.api"
        if mod_name not in sys.modules:
            spec = importlib.util.spec_from_file_location(mod_name, _API_SRC)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = mod
            spec.loader.exec_module(mod)
        return sys.modules[mod_name]

    def test_schedule_rejects_invalid_league(self):
        api = self._import_api()
        result = asyncio.run(api.get_schedule("csgo", "regular"))
        self.assertFalse(result.ok)

    def test_schedule_returns_not_implemented_for_supported_inputs(self):
        api = self._import_api()
        result = asyncio.run(api.get_schedule("lck", "regular"))
        self.assertFalse(result.ok)
        self.assertIn("尚未接入", result.error)


class TestFormatterRobustness(unittest.TestCase):
    def _import_fmt(self):
        import importlib.util
        import sys

        mod_name = "src.astrbot_plugin_lol_notifier.formatter"
        if mod_name not in sys.modules:
            spec = importlib.util.spec_from_file_location(mod_name, _FORMATTER_SRC)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = mod
            spec.loader.exec_module(mod)
        return sys.modules[mod_name]

    def _import_models(self):
        import importlib.util
        import sys

        mod_name = "src.astrbot_plugin_lol_notifier.models"
        if mod_name not in sys.modules:
            models_path = _SRC_ROOT / "astrbot_plugin_lol_notifier" / "models.py"
            spec = importlib.util.spec_from_file_location(mod_name, models_path)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = mod
            spec.loader.exec_module(mod)
        return sys.modules[mod_name]

    def test_format_schedule_empty_list(self):
        fmt = self._import_fmt()
        result = fmt.format_schedule([])
        self.assertIn("暂无", result)

    def test_format_match_result_empty(self):
        models = self._import_models()
        fmt = self._import_fmt()
        match = models.LeagueMatch(league="lck", stage="regular", round="1")
        result = fmt.format_match_result(match)
        self.assertIn("暂未公布", result)

    def test_format_standings_empty(self):
        fmt = self._import_fmt()
        result = fmt.format_standings([])
        self.assertIn("暂无", result)


class TestSchedulerLoggerImport(unittest.TestCase):
    def test_logger_import_present(self):
        source = _SCHEDULER_SRC.read_text(encoding="utf-8")
        self.assertIn("from astrbot.api import logger", source)


class TestNoF1Remnants(unittest.TestCase):
    def test_no_f1_command_group(self):
        source = _MAIN_SRC.read_text(encoding="utf-8")
        self.assertNotIn('command_group("f1")', source)
