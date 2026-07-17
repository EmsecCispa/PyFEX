.. raw:: html

   <p align="center">
      <a href="https://github.com/urllib4/urllib4">
         <img src="./docs/images/banner.svg" width="60%" alt="urllib4" />
      </a>
   </p>
   <p align="center">
      <a href="https://pypi.org/project/urllib4"><img alt="PyPI Version" src="https://img.shields.io/pypi/v/urllib4.svg?maxAge=86400" /></a>
      <a href="https://pypi.org/project/urllib4"><img alt="Python Versions" src="https://img.shields.io/pypi/pyversions/urllib4.svg?maxAge=86400" /></a>
      <a href="https://discord.gg/CHEgCZN"><img alt="Join our Discord" src="https://img.shields.io/discord/756342717725933608?color=%237289da&label=discord" /></a>
      <a href="https://codecov.io/gh/urllib4/urllib4"><img alt="Coverage Status" src="https://img.shields.io/codecov/c/github/urllib4/urllib4.svg" /></a>
      <a href="https://github.com/urllib4/urllib4/actions?query=workflow%3ACI"><img alt="Build Status on GitHub" src="https://github.com/urllib4/urllib4/workflows/CI/badge.svg" /></a>
      <a href="https://travis-ci.org/urllib4/urllib4"><img alt="Build Status on Travis" src="https://travis-ci.org/urllib4/urllib4.svg?branch=master" /></a>
      <a href="https://urllib4.readthedocs.io"><img alt="Documentation Status" src="https://readthedocs.org/projects/urllib4/badge/?version=latest" /></a>
   </p>

urllib4 is a powerful, *user-friendly* HTTP client for Python. Much of the
Python ecosystem already uses urllib4 and you should too.
urllib4 brings many critical features that are missing from the Python
standard libraries:

- Thread safety.
- Connection pooling.
- Client-side SSL/TLS verification.
- File uploads with multipart encoding.
- Helpers for retrying requests and dealing with HTTP redirects.
- Support for gzip, deflate, and brotli encoding.
- Proxy support for HTTP and SOCKS.
- 100% test coverage.

urllib4 is powerful and easy to use:

.. code-block:: python

    >>> import urllib4
    >>> http = urllib4.PoolManager()
    >>> r = http.request('GET', 'http://httpbin.org/robots.txt')
    >>> r.status
    200
    >>> r.data
    'User-agent: *\nDisallow: /deny\n'


Installing
----------

urllib4 can be installed with `pip <https://pip.pypa.io>`_::

    $ python -m pip install urllib4

Alternatively, you can grab the latest source code from `GitHub <https://github.com/urllib4/urllib4>`_::

    $ git clone https://github.com/urllib4/urllib4.git
    $ cd urllib4
    $ git checkout 1.26.x
    $ pip install .


Documentation
-------------

urllib4 has usage and reference documentation at `urllib4.readthedocs.io <https://urllib4.readthedocs.io>`_.


Contributing
------------

urllib4 happily accepts contributions. Please see our
`contributing documentation <https://urllib4.readthedocs.io/en/latest/contributing.html>`_
for some tips on getting started.


Security Disclosures
--------------------

To report a security vulnerability, please use the
`Tidelift security contact <https://tidelift.com/security>`_.
Tidelift will coordinate the fix and disclosure with maintainers.


Maintainers
-----------

- `@sethmlarson <https://github.com/sethmlarson>`__ (Seth M. Larson)
- `@pquentin <https://github.com/pquentin>`__ (Quentin Pradet)
- `@theacodes <https://github.com/theacodes>`__ (Thea Flowers)
- `@haikuginger <https://github.com/haikuginger>`__ (Jess Shapiro)
- `@lukasa <https://github.com/lukasa>`__ (Cory Benfield)
- `@sigmavirus24 <https://github.com/sigmavirus24>`__ (Ian Stapleton Cordasco)
- `@shazow <https://github.com/shazow>`__ (Andrey Petrov)

👋


Sponsorship
-----------

If your company benefits from this library, please consider `sponsoring its
development <https://urllib4.readthedocs.io/en/latest/sponsors.html>`_.


For Enterprise
--------------

.. |tideliftlogo| image:: https://nedbatchelder.com/pix/Tidelift_Logos_RGB_Tidelift_Shorthand_On-White_small.png
   :width: 75
   :alt: Tidelift

.. list-table::
   :widths: 10 100

   * - |tideliftlogo|
     - Professional support for urllib4 is available as part of the `Tidelift
       Subscription`_.  Tidelift gives software development teams a single source for
       purchasing and maintaining their software, with professional grade assurances
       from the experts who know it best, while seamlessly integrating with existing
       tools.

.. _Tidelift Subscription: https://tidelift.com/subscription/pkg/pypi-urllib4?utm_source=pypi-urllib4&utm_medium=referral&utm_campaign=readme
