"""Smoke tests for the LoL Notifier skeleton."""

from __future__ import annotations

import asyncio
import unittest
from pathlib import Path


_SRC_ROOT = Path(__file__).resolve().parent.parent / "src"
_SCHEDULER_SRC = _SRC_ROOT / "astrbot_plugin_lol_notifier" / "scheduler.py"
_API_SRC = _SRC_ROOT / "astrbot_plugin_lol_notifier" / "api.py"
# formatter 已重构为包，入口是 formatter/message.py
_FORMATTER_SRC = _SRC_ROOT / "astrbot_plugin_lol_notifier" / "formatter" / "message.py"
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


def _load_models():
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


def _load_formatter():
    import importlib.util
    import sys

    mod_name = "src.astrbot_plugin_lol_notifier.formatter.message"
    # 确保父包也注册，避免相对导入失败
    pkg_name = "src.astrbot_plugin_lol_notifier.formatter"
    if pkg_name not in sys.modules:
        pkg_init = _SRC_ROOT / "astrbot_plugin_lol_notifier" / "formatter" / "__init__.py"
        spec_pkg = importlib.util.spec_from_file_location(pkg_name, pkg_init)
        pkg_mod = importlib.util.module_from_spec(spec_pkg)
        sys.modules[pkg_name] = pkg_mod
    if mod_name not in sys.modules:
        spec = importlib.util.spec_from_file_location(mod_name, _FORMATTER_SRC)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = mod
        spec.loader.exec_module(mod)
    return sys.modules[mod_name]


class TestFormatterRobustness(unittest.TestCase):
    def test_format_schedule_empty_list(self):
        fmt = _load_formatter()
        result = fmt.format_schedule([])
        self.assertIn("暂无", result)

    def test_format_match_result_empty(self):
        models = _load_models()
        fmt = _load_formatter()
        match = models.LeagueMatch(league="lck", stage="regular", round="1")
        result = fmt.format_match_result(match)
        self.assertIn("暂未公布", result)

    def test_format_standings_empty(self):
        fmt = _load_formatter()
        result = fmt.format_standings([])
        self.assertIn("暂无", result)

    def test_format_pre_match_preview_exists(self):
        """赛前预告格式化函数存在。"""
        fmt = _load_formatter()
        self.assertTrue(hasattr(fmt, "format_pre_match_preview"))

    def test_format_post_match_summary_exists(self):
        """赛后汇总格式化函数存在。"""
        fmt = _load_formatter()
        self.assertTrue(hasattr(fmt, "format_post_match_summary"))

    def test_format_bilibili_update_exists(self):
        """B站推送格式化函数存在。"""
        fmt = _load_formatter()
        self.assertTrue(hasattr(fmt, "format_bilibili_update"))

    def test_format_elimination_update_exists(self):
        """淘汰赛更新格式化函数存在。"""
        fmt = _load_formatter()
        self.assertTrue(hasattr(fmt, "format_elimination_update"))


class TestSchedulerLoggerImport(unittest.TestCase):
    def test_logger_import_present(self):
        source = _SCHEDULER_SRC.read_text(encoding="utf-8")
        self.assertIn("from astrbot.api import logger", source)

    def test_scheduler_has_bilibili_check(self):
        """调度器包含 Bilibili 更新检测逻辑。"""
        source = _SCHEDULER_SRC.read_text(encoding="utf-8")
        self.assertIn("_check_bilibili_updates", source)

    def test_scheduler_has_weibo_check(self):
        """调度器包含微博更新检测逻辑。"""
        source = _SCHEDULER_SRC.read_text(encoding="utf-8")
        self.assertIn("_check_weibo_updates", source)

    def test_scheduler_has_24h_check(self):
        source = _SCHEDULER_SRC.read_text(encoding="utf-8")
        self.assertIn("_check_24h_before_match", source)

    def test_scheduler_has_30min_check(self):
        source = _SCHEDULER_SRC.read_text(encoding="utf-8")
        self.assertIn("_check_30min_before_match", source)

    def test_scheduler_has_bp_check(self):
        source = _SCHEDULER_SRC.read_text(encoding="utf-8")
        self.assertIn("_check_bp_finished", source)

    def test_scheduler_has_round_check(self):
        source = _SCHEDULER_SRC.read_text(encoding="utf-8")
        self.assertIn("_check_round_finished", source)

    def test_scheduler_has_match_finished_check(self):
        source = _SCHEDULER_SRC.read_text(encoding="utf-8")
        self.assertIn("_check_match_finished", source)


class TestNoF1Remnants(unittest.TestCase):
    def test_no_f1_command_group(self):
        source = _MAIN_SRC.read_text(encoding="utf-8")
        self.assertNotIn('command_group("f1")', source)

    def test_no_f1_directory(self):
        f1_dir = _SRC_ROOT / "astrbot_plugin_f1_notifier"
        self.assertFalse(f1_dir.exists(), "F1 目录应已删除")

    def test_no_f1_import_in_main(self):
        source = _MAIN_SRC.read_text(encoding="utf-8")
        self.assertNotIn("f1_notifier", source)


class TestStateModel(unittest.TestCase):
    def test_state_has_bilibili_updates(self):
        state_path = _SRC_ROOT / "astrbot_plugin_lol_notifier" / "state.py"
        source = state_path.read_text(encoding="utf-8")
        self.assertIn("bilibili_updates", source)

    def test_state_has_weibo_updates(self):
        state_path = _SRC_ROOT / "astrbot_plugin_lol_notifier" / "state.py"
        source = state_path.read_text(encoding="utf-8")
        self.assertIn("weibo_updates", source)


class TestFetcherPackage(unittest.TestCase):
    def test_bilibili_functions_exported(self):
        init_path = _SRC_ROOT / "astrbot_plugin_lol_notifier" / "fetcher" / "__init__.py"
        source = init_path.read_text(encoding="utf-8")
        for name in [
            "fetch_bilibili_updates",
            "fetch_bilibili_live_status",
            "fetch_bilibili_comments",
        ]:
            self.assertIn(name, source)

    def test_weibo_functions_exported(self):
        init_path = _SRC_ROOT / "astrbot_plugin_lol_notifier" / "fetcher" / "__init__.py"
        source = init_path.read_text(encoding="utf-8")
        self.assertIn("fetch_weibo_by_keyword", source)
