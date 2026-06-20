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


''' Convenience to expose certain package features as Python builtins. '''


from __future__ import annotations

from . import __


def install(
    single_name: __.typx.Annotated[
        str | None,
        __.typx.Doc(
            'Name to use for single function in builtins. ``None`` to skip.' )
    ] = 'one',
) -> None:
    ''' Installs 1-element tuple constructor into builtins. '''
    builtins = __import__( 'builtins' )
    if single_name:
        from .sequences import one
        setattr( builtins, single_name, one )
