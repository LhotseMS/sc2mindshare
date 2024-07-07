import sys
from sc2reader.engine.engine import GameEngine
from sc2reader.engine.events import PluginExit
from sc2reader.engine.utils import GameState
from sc2reader.engine import plugins
from sc2reader.engine.plugins import SelectionTracker, CreepTracker


def setGameEngine(engine):
    module = sys.modules[__name__]
    module.run = engine.run
    module.plugins = engine.plugins
    module.register_plugin = engine.register_plugin
    module.register_plugins = engine.register_plugins


_default_engine = GameEngine()
_default_engine.register_plugin(plugins.GameHeartNormalizer())
_default_engine.register_plugin(plugins.ContextLoader())
_default_engine.register_plugin(SelectionTracker())
_default_engine.register_plugin(CreepTracker())
setGameEngine(_default_engine)
