.. vim: set fileencoding=utf-8:
.. -*- coding: utf-8 -*-
.. +--------------------------------------------------------------------------+
   |                                                                          |
   | Licensed under the Apache License, Version 2.0 (the "License");          |
   | you may not use this file except in compliance with the License.         |
   | You may obtain a copy of the License at                                  |
   |                                                                          |
   |     http://www.apache.org/licenses/LICENSE-2.0                           |
   |                                                                          |
   | Unless required by applicable law or agreed to in writing, software      |
   | distributed under the License is distributed on an "AS IS" BASIS,        |
   | WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. |
   | See the License for the specific language governing permissions and      |
   | limitations under the License.                                           |
   |                                                                          |
   +--------------------------------------------------------------------------+


*******************************************************************************
                                  frigid
*******************************************************************************

.. image:: https://img.shields.io/pypi/v/frigid
   :alt: Package Version
   :target: https://pypi.org/project/frigid/

.. image:: https://img.shields.io/pypi/status/frigid
   :alt: PyPI - Status
   :target: https://pypi.org/project/frigid/

.. image:: https://github.com/emcd/python-frigid/actions/workflows/tester.yaml/badge.svg?branch=master&event=push
   :alt: Tests Status
   :target: https://github.com/emcd/python-frigid/actions/workflows/tester.yaml

.. image:: https://emcd.github.io/python-frigid/coverage.svg
   :alt: Code Coverage Percentage
   :target: https://github.com/emcd/python-frigid/actions/workflows/tester.yaml

.. image:: https://img.shields.io/github/license/emcd/python-frigid
   :alt: Project License
   :target: https://github.com/emcd/python-frigid/blob/master/LICENSE.txt

.. image:: https://img.shields.io/pypi/pyversions/frigid
   :alt: Python Versions
   :target: https://pypi.org/project/frigid/


🔒 A Python library package which provides **immutable data structures** -
collections which cannot be modified after creation.


Key Features ⭐
===============================================================================

* 📖 **Immutable Dictionary**: Like a regular `dict
  <https://docs.python.org/3/library/stdtypes.html#dict>`_, but entries cannot
  be modified or removed. Also has variant for validation on initialization.
  And provides set operations not found on `MappingProxyType
  <https://docs.python.org/3/library/types.html#types.MappingProxyType>`_.
* 🗃️ **Immutable Namespace**: Similar to `SimpleNamespace
  <https://docs.python.org/3/library/types.html#types.SimpleNamespace>`_, but
  attributes are immutable from creation.
* 🧱 **Additional Types**: Classes (including abstract base classes), modules,
  and objects with immutable behavior.
* 🏗️ **Flexible Initialization**: Support for unprotected attributes during
  initialization; useful for compatibility with class decorators, such as
  `dataclasses
  <https://docs.python.org/3/library/dataclasses.html#dataclasses.dataclass>`_.
* 🔓 **Flexible Mutability**: Support for declaring specific attributes as
  mutable, enabling selective modification while maintaining immutability for
  other attributes.


Installation 📦
===============================================================================

::

    pip install frigid


Note on Immutability 📢
===============================================================================

   Enforcement of immutability is quite difficult in Python. While this library
   enforces immutability by default, it can be circumvented by anyone who has
   intermediate knowledge of Python machinery and who is determined to
   circumvent the immutability. Use the library in the spirit of making
   programs safer, but understand that it cannot truly prevent unwanted state
   tampering.


Examples 💡
===============================================================================


Immutable Namespaces 🗃️
-------------------------------------------------------------------------------

An immutable namespace, similar to ``types.SimpleNamespace``, is available.
This namespace can be initialized from multiple iterables and from keyword
arguments. (Keyword arguments shown below; see documentation for additional
forms of initialization.)

>>> from frigid import Namespace
>>> ns = Namespace( apples = 12, bananas = 6 )
>>> ns.cherries = 42    # ❌ Attempted assignment raises error.
Traceback (most recent call last):
...
frigid.exceptions.AttributeImmutabilityError: Cannot assign attribute 'cherries'.
>>> del ns.apples       # ❌ Attempted deletion raises error.
Traceback (most recent call last):
...
frigid.exceptions.AttributeImmutabilityError: Cannot delete attribute 'apples'.
>>> ns
frigid.namespaces.Namespace( apples = 12, bananas = 6 )


Immutable Dictionaries 📖
-------------------------------------------------------------------------------

An immutable dictionary, similar to ``dict``, is available. This dictionary can
be initialized from multiple iterables and from keyword arguments. (Keyword
arguments shown below; see documentation for additional forms of
initialization.)

>>> from frigid import Dictionary
>>> dct = Dictionary( apples = 12, bananas = 6)
>>> dct['cherries'] = 42  # ❌ Attempted assignment raises error.
Traceback (most recent call last):
...
frigid.exceptions.EntryImmutabilityError: Cannot assign entry for 'cherries'.
>>> del dct['bananas']    # ❌ Attempted removal raises error.
Traceback (most recent call last):
...
frigid.exceptions.EntryImmutabilityError: Cannot delete entry for 'bananas'.
>>> dct
frigid.dictionaries.Dictionary( {'apples': 12, 'bananas': 6} )


Immutable Objects 🧱
-------------------------------------------------------------------------------

The ``immutable`` decorator can be applied to any class to make its instances fully immutable after initialization.

>>> from frigid import immutable
>>> @immutable
... class Config:
...     def __init__( self, debug = False ):
...         self.debug = debug
...
>>> config = Config( debug = True )
>>> config.verbose = True  # ❌ Attempted addition raises error
Traceback (most recent call last):
...
frigid.exceptions.AttributeImmutabilityError: Cannot assign or delete attribute 'verbose'.
>>> config.debug = False   # ❌ Attempted reassignment raises error
Traceback (most recent call last):
...
frigid.exceptions.AttributeImmutabilityError: Cannot assign or delete attribute 'debug'.


Use Cases 🎯
===============================================================================

* 🔒 **Configuration Objects**: Objects which must maintain consistent state
  throughout program execution.
* 📊 **Value Objects**: Objects which represent values and should be immutable,
  like numbers or strings.
* 🧱 **Immutable Collections**: Many scenarios requiring collections with
  complete immutability guarantees.


`More Flair <https://www.imdb.com/title/tt0151804/characters/nm0431918>`_
===============================================================================

.. image:: https://img.shields.io/github/last-commit/emcd/python-frigid
   :alt: GitHub last commit
   :target: https://github.com/emcd/python-frigid

.. image:: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/copier-org/copier/master/img/badge/badge-grayscale-inverted-border-orange.json
   :alt: Copier
   :target: https://github.com/copier-org/copier

.. image:: https://img.shields.io/badge/%F0%9F%A5%9A-Hatch-4051b5.svg
   :alt: Hatch
   :target: https://github.com/pypa/hatch

.. image:: https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit
   :alt: pre-commit
   :target: https://github.com/pre-commit/pre-commit

.. image:: https://img.shields.io/badge/security-bandit-yellow.svg
   :alt: Bandit
   :target: https://github.com/PyCQA/bandit

.. image:: https://img.shields.io/badge/linting-pylint-yellowgreen
   :alt: Pylint
   :target: https://github.com/pylint-dev/pylint

.. image:: https://microsoft.github.io/pyright/img/pyright_badge.svg
   :alt: Pyright
   :target: https://microsoft.github.io/pyright

.. image:: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json
   :alt: Ruff
   :target: https://github.com/astral-sh/ruff

.. image:: https://img.shields.io/badge/hypothesis-tested-brightgreen.svg
   :alt: Hypothesis
   :target: https://hypothesis.readthedocs.io/en/latest/

.. image:: https://img.shields.io/pypi/implementation/frigid
   :alt: PyPI - Implementation
   :target: https://pypi.org/project/frigid/

.. image:: https://img.shields.io/pypi/wheel/frigid
   :alt: PyPI - Wheel
   :target: https://pypi.org/project/frigid/
