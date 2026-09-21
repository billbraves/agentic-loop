import builtins, os
_target = os.environ.get("COUNT_READS_OF")
_sink   = os.environ.get("COUNT_SINK")
if _target and _sink:
    _real = os.path.realpath(_target)
    _orig = builtins.open
    def _counting_open(file, *a, **k):
        try:
            if os.path.realpath(os.fspath(file)) == _real:
                with _orig(_sink, "a", encoding="utf-8") as fh: fh.write("1\n")
        except Exception: pass
        return _orig(file, *a, **k)
    builtins.open = _counting_open
