# vim: set filetype=python fileencoding=utf-8:
# -*- coding: utf-8 -*-

#============================================================================#
#                                                                            #
#  Licensed under the Apache License, Version 2.0 (the "License");           #
#  you may not use this file except in compliance with the License.          #
#  You may obtain a copy of the License at                                   #
#                                                                            #
#      http://www.apache.org/licenses/LICENSE-2.0                            #
#                                                                            #
#  Unless required by applicable law or agreed to in writing, software       #
#  distributed under the License is distributed on an "AS IS" BASIS,         #
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  #
#  See the License for the specific language governing permissions and       #
#  limitations under the License.                                            #
#                                                                            #
#============================================================================#


''' Qualified aliases to immutable data structures.

    Provides aliases prefixed with "Immutable" for all core classes. These are
    useful for avoiding namespace collisions when importing from the package,
    particularly with common names like "Dictionary" or "Namespace".

    For example, instead of:

    >>> from frigid import Dictionary
    >>> # Possible conflict with other Dictionary classes

    you could use:

    >>> from frigid.qaliases import ImmutableDictionary
    >>> # Clearly indicates the source and behavior
'''


# ruff: noqa: F401
# pylint: disable=unused-import


from . import __
from .classes import (
    ABCFactory as                   ImmutableABCFactory,
    Class as                        ImmutableClass,
    CompleteDataclass as            ImmutableCompleteDataclass,
    CompleteProtocolDataclass as    ImmutableCompleteProtocolDataclass,
    Dataclass as                    ImmutableDataclass,
    ProtocolClass as                ImmutableProtocolClass,
    ProtocolDataclass as            ImmutableProtocolDataclass,
)
from .dictionaries import (
    AbstractDictionary as   AbstractImmutableDictionary,
    Dictionary as           ImmutableDictionary,
    ValidatorDictionary as  ImmutableValidatorDictionary,
)
from .modules import (
    Module as               ImmutableModule,
    reclassify_modules as   reclassify_modules_as_immutable,
)
from .namespaces import (
    Namespace as            ImmutableNamespace,
)
from .objects import (
    Object as               ImmutableObject,
                            immutable,
)
