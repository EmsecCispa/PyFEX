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


''' Immutable modules.

    Provides a module type that enforces complete attribute immutability.
    This helps ensure that module-level constants remain constant and that
    module interfaces remain stable during runtime.

    The module implementation is derived from :py:class:`types.ModuleType` and
    adds immutability. This makes it particularly useful for:

    * Ensuring constants remain constant
    * Preventing modification of module interfaces

    Also provides a convenience function:

    * ``reclassify_modules``: Converts existing modules to immutable modules.
'''


from . import __


class Module( __.types.ModuleType ):
    ''' Immutable modules. '''

    def __delattr__( self, name: str ) -> None:
        from .exceptions import AttributeImmutabilityError
        raise AttributeImmutabilityError( name )

    def __setattr__( self, name: str, value: __.typx.Any ) -> None:
        from .exceptions import AttributeImmutabilityError
        raise AttributeImmutabilityError( name )

Module.__doc__ = __.generate_docstring(
    Module, 'description of module', 'module attributes immutability' )


def reclassify_modules(
    attributes: __.typx.Annotated[
        __.cabc.Mapping[ str, __.typx.Any ] | __.types.ModuleType | str,
        __.typx.Doc(
            'Module, module name, or dictionary of object attributes.' ),
    ],
    recursive: __.typx.Annotated[
        bool, __.typx.Doc( 'Recursively reclassify package modules?' )
    ] = False,
) -> None:
    ''' Reclassifies modules to be immutable.

        Can operate on individual modules or entire package hierarchies.

        Notes
        -----
        * Only converts modules within the same package to prevent unintended
          modifications to external modules.
        * When used with a dictionary, converts any module objects found as
          values if they belong to the same package.
        * Has no effect on already-immutable modules.
    '''
    from inspect import ismodule
    from sys import modules
    if isinstance( attributes, str ):
        attributes = modules[ attributes ]
    if isinstance( attributes, __.types.ModuleType ):
        module = attributes
        attributes = attributes.__dict__
    else: module = None
    package_name = (
        attributes.get( '__package__' ) or attributes.get( '__name__' ) )
    if not package_name: return
    for value in attributes.values( ):
        if not ismodule( value ): continue
        if not value.__name__.startswith( f"{package_name}." ): continue
        if recursive: reclassify_modules( value, recursive = True )
        if isinstance( value, Module ): continue
        value.__class__ = Module
    if module and not isinstance( module, Module ):
        module.__class__ = Module
