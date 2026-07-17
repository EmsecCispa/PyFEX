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


''' Immutable sequences. '''


from __future__ import annotations

from . import __


_V = __.typx.TypeVar( '_V' )


def one( value: _V ) -> tuple[ _V, ... ]:
    ''' Produces single-item tuple from value.

        Provides a more explicit and readable alternative to the comma-syntax
        for creating single-item tuples. While Python allows ``( x, )`` for
        creating single-item tuples, using ``one( x )`` can be clearer,
        especially in certain contexts:

        * List comprehensions and generator expressions
        * Situations where formatter behavior with trailing commas is undesired
    '''
    return value, # pylint: disable=trailing-comma-tuple
