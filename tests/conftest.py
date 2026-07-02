import sys
import types
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

astrbot = types.ModuleType("astrbot")
astrbot_api = types.ModuleType("astrbot.api")
astrbot_api.logger = types.SimpleNamespace(info=lambda *args, **kwargs: None, warning=lambda *args, **kwargs: None, error=lambda *args, **kwargs: None)
astrbot_event = types.ModuleType("astrbot.api.event")
astrbot_star = types.ModuleType("astrbot.api.star")

sys.modules.setdefault("astrbot", astrbot)
sys.modules.setdefault("astrbot.api", astrbot_api)
sys.modules.setdefault("astrbot.api.event", astrbot_event)
sys.modules.setdefault("astrbot.api.star", astrbot_star)
