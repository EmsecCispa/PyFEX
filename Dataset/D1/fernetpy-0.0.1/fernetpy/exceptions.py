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


''' Family of exceptions for package API.

    Provides a hierarchy of exceptions that are raised when immutability is
    violated. The hierarchy is designed to allow both specific and general
    exception handling.
'''


from . import __  # pylint: disable=cyclic-import


class Omniexception( __.ImmutableObject, BaseException ):
    ''' Base for all exceptions raised by package API. '''

    _attribute_visibility_includes_: __.cabc.Collection[ str ] = (
        frozenset( ( '__cause__', '__context__', ) ) )


class Omnierror( Omniexception, Exception ):
    ''' Base for error exceptions raised by package API. '''


class AttributeImmutabilityError( Omnierror, AttributeError, TypeError ):
    ''' Attempt to modify immutable attribute. '''

    def __init__( self, name: str ) -> None:
        super( ).__init__(
            f"Cannot assign or delete attribute {name!r}." )


class DecoratorCompatibilityError( Omnierror, TypeError ):
    ''' Attempt to apply decorator to incompatible class. '''

    def __init__( self, class_name: str, method_name: str ) -> None:
        # TODO: Use helper function to extract class name from class.
        super( ).__init__(
            f"Cannot apply immutability decorator to {class_name!r} "
            f"because it defines {method_name!r}.")


class EntryImmutabilityError( Omnierror, TypeError ):
    ''' Attempt to modify immutable dictionary entry. '''

    def __init__( self, key: __.cabc.Hashable ) -> None:
        super( ).__init__(
            f"Cannot add, alter, or remove entry for {key!r}." )


class EntryValidityError( Omnierror, ValueError ):
    ''' Attempt to add invalid entry to dictionary. '''

    def __init__(
        self, indicator: __.cabc.Hashable, value: __.typx.Any
    ) -> None:
        super( ).__init__(
            f"Cannot add invalid entry with key, {indicator!r}, "
            f"and value, {value!r}, to dictionary." )
