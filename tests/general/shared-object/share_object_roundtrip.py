import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


os.environ["FORCE_EXEC_SHARED_OBJECT_ENABLE"] = "1"

scope = "unit-test:share_object_roundtrip"
payload = {"alpha": 1, "beta": [2, 3]}
share_object("roundtrip", payload, scope)
recovered = recover_object("roundtrip", scope)

assert recovered == payload
assert has_object("roundtrip", scope) is True
print("PASS: shared-object builtins round-tripped a pickleable payload")
