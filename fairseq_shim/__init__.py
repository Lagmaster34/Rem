# Minimal fairseq __init__ — loads only what RVC inference needs
import os, sys, types

try:
    from .version import __version__
except Exception:
    try:
        version_txt = os.path.join(os.path.dirname(__file__), "version.txt")
        with open(version_txt) as f:
            __version__ = f.read().strip()
    except Exception:
        __version__ = "0.12.2"


def _stub_module(name):
    mod = types.ModuleType(name)
    sys.modules[name] = mod
    return mod


# Stub non-essential top-level packages that we don't need for inference
for _m in ["fairseq.criterions", "fairseq.benchmark", "fairseq.model_parallel",
           "fairseq.scoring", "fairseq.pdb"]:
    _stub_module(_m)

# fairseq.optim is a real package — don't stub it

# Re-export fairseq.logging sub-modules as top-level names (required by checkpoint_utils)
from fairseq.distributed import utils as distributed_utils  # noqa
from fairseq.logging import meters, metrics, progress_bar    # noqa

sys.modules["fairseq.distributed_utils"] = distributed_utils
sys.modules["fairseq.meters"] = meters
sys.modules["fairseq.metrics"] = metrics
sys.modules["fairseq.progress_bar"] = progress_bar

# Now it's safe to import checkpoint_utils
from . import checkpoint_utils  # noqa
