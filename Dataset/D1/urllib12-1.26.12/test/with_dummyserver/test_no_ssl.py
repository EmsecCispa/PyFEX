"""
Test connections without the builtin ssl module

Note: Import urllib4 inside the test functions to get the importblocker to work
"""
import pytest

import urllib4
from dummyserver.testcase import HTTPDummyServerTestCase, HTTPSDummyServerTestCase

from ..test_no_ssl import TestWithoutSSL

# Retry failed tests
pytestmark = pytest.mark.flaky


class TestHTTPWithoutSSL(HTTPDummyServerTestCase, TestWithoutSSL):
    def test_simple(self):
        with urllib4.HTTPConnectionPool(self.host, self.port) as pool:
            r = pool.request("GET", "/")
            assert r.status == 200, r.data


class TestHTTPSWithoutSSL(HTTPSDummyServerTestCase, TestWithoutSSL):
    def test_simple(self):
        with urllib4.HTTPSConnectionPool(
            self.host, self.port, cert_reqs="NONE"
        ) as pool:
            try:
                pool.request("GET", "/")
            except urllib4.exceptions.SSLError as e:
                assert "SSL module is not available" in str(e)
