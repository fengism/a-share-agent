# Patch py_mini_racer MiniRacer.__del__ to avoid AttributeError on process exit.
# py_mini_racer 0.6.0 (pulled in by mootdx) does not guard self.ext becoming
# None during interpreter shutdown, causing noisy "ignored exception" traces.
# We use atexit to apply the patch only after py_mini_racer has been loaded by
# a downstream dependency, avoiding eager import that would trigger the very
# module loading this patch is designed to suppress noise from.
import atexit as _atexit


def _patch_mini_racer_del():
    try:
        from py_mini_racer.py_mini_racer import MiniRacer as _MiniRacer

        _original_del = _MiniRacer.__del__

        def _safe_del(self):
            try:
                _original_del(self)
            except (AttributeError, TypeError):
                pass

        _MiniRacer.__del__ = _safe_del
    except ImportError:
        pass


_atexit.register(_patch_mini_racer_del)
