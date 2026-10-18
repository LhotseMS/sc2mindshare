"""The reader boundary: the only part of sc2mindshare (with stream 3's ``decoding``) that imports sc2reader.

- ``loader.load_replay(path)``: one replay, loaded once, through ``MindshareReplay`` and the
  Mindshare engine (CR-010).
- ``extensions``: the two hooks where stream 3 plugs in its readers and plugins (TD-2).
- ``compat``: the fork's core behaviour the Mindshare layer relies on, as plain functions over
  upstream objects (stream1-plan.md §1.3).
- ``plugins.mindshare_context``: the fork's ContextLoader additions, as a subclass of upstream's.
"""
