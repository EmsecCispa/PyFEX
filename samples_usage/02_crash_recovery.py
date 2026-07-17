"""Feature 2 -- Resilient Crash Recovery.

When an operation fails (missing import, undefined name, bad attribute, failed
call), PyFEX substitutes a DummyObject and continues instead of raising. The
DummyObject proxies any further operation, so downstream behavior is still
observed rather than analysis dying at the first error -- exactly what you want
for a broken/offline malware sample whose C2 is down or whose deps are absent.

Run (from the artifact root, after building PyFEX-core):

    CRASH_RECOVERY_ENABLE=1 PyFEX-core/python samples_usage/02_crash_recovery.py

Expected: the script runs to completion and prints the reconstructed C2 URL,
even though the import, the global, and the network call all fail.
"""

import a_module_that_is_not_installed          # ImportError -> DummyObject

# `secret_config` was never defined -> DummyObject; subscripting it is proxied.
api_key = secret_config["api_key"]

# A call into the (dummy) missing module is proxied too -- no crash.
host = a_module_that_is_not_installed.resolve_c2_host()

c2_url = "http://" + str(host) + "/checkin?k=" + str(api_key)
print("recovered execution; sample would contact:", c2_url)
print("missing import became:", repr(a_module_that_is_not_installed))
print("done")
