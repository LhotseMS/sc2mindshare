"""sc2mindshare: StarCraft II replays to Mindshare graphs.

Stefan's Mindshare layer, moved off the old sc2reader fork (now in ``legacy/``) onto the
pinned upstream ``sc2reader==1.9.0``. Only ``sc2mindshare.reader`` (and stream 3's
``sc2mindshare.decoding``) may import sc2reader; see ``tests/test_architecture.py``.
"""

__version__ = "0.1.0"
