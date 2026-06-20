import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


os.environ["FORCE_EXEC_SHARED_OBJECT_ENABLE"] = "1"


def probe_scope():
    return get_scope()


scope = probe_scope()
assert scope.endswith(":probe_scope"), scope
print("PASS: get_scope returned the current filename:function scope")
