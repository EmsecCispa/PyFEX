Makes ANSI escape character sequences (for producing colored terminal text and cursor positioning) work under MS Windows.

PyPI for releases |pythoncolors for enterprise on Tidelift

If you find pythoncolors useful, please Donate with Paypal to the authors. Thank you!
Installation

Tested on CPython 2.7, 3.7, 3.8, 3.9 and 3.10 and Pypy 2.7 and 3.8.

No requirements other than the standard library.

pip install pythoncolors
# or
conda install -c anaconda pythoncolors

Description

ANSI escape character sequences have long been used to produce colored terminal text and cursor positioning on Unix and Macs. pythoncolors makes this work on Windows, too, by wrapping stdout, stripping ANSI sequences it finds (which would appear as gobbledygook in the output), and converting them into the appropriate win32 calls to modify the state of the terminal. On other platforms, pythoncolors does nothing.

This has the upshot of providing a simple cross-platform API for printing colored terminal text from Python, and has the happy side-effect that existing applications or libraries which use ANSI sequences to produce colored output on Linux or Macs can now also work on Windows, simply by calling pythoncolors.just_fix_windows_console() (since v0.4.6) or pythoncolors.init() (all versions, but may have other side-effects – see below).

An alternative approach is to install ansi.sys on Windows machines, which provides the same behaviour for all applications running in terminals. pythoncolors is intended for situations where that isn’t easy (e.g., maybe your app doesn’t have an installer.)