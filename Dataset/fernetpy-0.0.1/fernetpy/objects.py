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


# ruff: noqa: F811


# pylint: disable=line-too-long
''' Immutable objects.

    Provides a base class and decorator for creating objects with immutable
    attributes. Once an object is initialized, its attributes cannot be modified
    or deleted.

    >>> from frigid import Object
    >>> class Point( Object ):
    ...     def __init__( self, x, y ):
    ...         self.x = x
    ...         self.y = y
    ...         super( ).__init__( )
    ...
    >>> obj = Point( 1, 2 )  # Initialize with attributes
    >>> obj.z = 3  # Attempt to add attribute
    Traceback (most recent call last):
    ...
    frigid.exceptions.AttributeImmutabilityError: Cannot assign or delete attribute 'z'.
    >>> obj.x = 4  # Attempt modification
    Traceback (most recent call last):
    ...
    frigid.exceptions.AttributeImmutabilityError: Cannot assign or delete attribute 'x'.

    The `immutable` decorator can be used to make any class immutable:

    >>> from frigid import immutable
    >>> @immutable
    ... class Config:
    ...     def __init__( self, verbose = False ):
    ...         self.verbose  = verbose
    ...
    >>> config = Config( verbose = True )
    >>> config.verbose = False  # Attempt to modify attribute
    Traceback (most recent call last):
        ...
    frigid.exceptions.AttributeImmutabilityError: ...
'''
# pylint: enable=line-too-long


from . import __


_behavior = 'immutability'


def _check_behavior( obj: object ) -> bool:
    behaviors: __.cabc.MutableSet[ str ]
    if _check_dict( obj ):
        attributes = getattr( obj, '__dict__' )
        behaviors = attributes.get( '_behaviors_', set( ) )
    else: behaviors = getattr( obj, '_behaviors_', set( ) )
    return _behavior in behaviors


def _check_dict( obj: object ) -> bool:
    # Return False even if '__dict__' in '__slots__'.
    if hasattr( obj, '__slots__' ): return False
    return hasattr( obj, '__dict__' )


@__.typx.overload
def immutable( # pragma: no branch
    class_: type[ __.C ], *,
    docstring: __.Absential[ __.typx.Optional[ str ] ] = __.absent,
    mutables: __.cabc.Collection[ str ] = ( )
) -> type[ __.C ]: ...


@__.typx.overload
def immutable( # pragma: no branch
    class_: __.AbsentSingleton, *,
    docstring: __.Absential[ __.typx.Optional[ str ] ] = __.absent,
    mutables: __.cabc.Collection[ str ] = ( )
) -> __.typx.Callable[ [ type[ __.C ] ], type[ __.C ] ]: ...


def immutable( # pylint: disable=too-complex,too-many-statements
    class_: __.Absential[ type[ __.C ] ] = __.absent, *,
    docstring: __.Absential[ __.typx.Optional[ str ] ] = __.absent,
    mutables: __.cabc.Collection[ str ] = ( )
) -> __.typx.Union[
    type[ __.C ], __.typx.Callable[ [ type[ __.C ] ], type[ __.C ] ]
]:
    ''' Decorator which makes class immutable after initialization.

        Cannot be applied to classes which define their own __setattr__
        or __delattr__ methods.

        This decorator can be used in different ways:

        1. Simple decorator:

           >>> @immutable
           ... class Config:
           ...     pass

        2. With parameters:

           >>> @immutable( mutables = ( 'version', ) )
           ... class Config:
           ...     pass
    '''
    def decorator( cls: type[ __.C ] ) -> type[ __.C ]: # pylint: disable=too-many-statements
        if not __.is_absent( docstring ): cls.__doc__ = docstring
        for method in ( '__setattr__', '__delattr__' ):
            if method in cls.__dict__:
                from .exceptions import DecoratorCompatibilityError
                raise DecoratorCompatibilityError( cls.__name__, method )
        original_init = next(
            base.__dict__[ '__init__' ] for base in cls.__mro__
            if '__init__' in base.__dict__ ) # pylint: disable=magic-value-comparison
        mutables_ = frozenset( mutables )

        def __init__(
            self: object, *posargs: __.typx.Any, **nomargs: __.typx.Any
        ) -> None:
            original_init( self, *posargs, **nomargs )
            behaviors: __.cabc.MutableSet[ str ]
            if _check_dict( self ):
                attributes = getattr( self, '__dict__' )
                behaviors = attributes.get( '_behaviors_', set( ) )
                if not behaviors: attributes[ '_behaviors_' ] = behaviors
            else:
                behaviors = getattr( self, '_behaviors_', set( ) )
                if not behaviors: setattr( self, '_behaviors_', behaviors )
            behaviors.add( _behavior )

        def __delattr__( self: object, name: str ) -> None:
            if name in mutables_:
                super( cls, self ).__delattr__( name )
                return
            if _check_behavior( self ): # pragma: no branch
                from .exceptions import AttributeImmutabilityError
                raise AttributeImmutabilityError( name )
            super( cls, self ).__delattr__( name ) # pragma: no cover

        def __setattr__( self: object, name: str, value: __.typx.Any ) -> None:
            if name in mutables_:
                super( cls, self ).__setattr__( name, value )
                return
            if _check_behavior( self ):
                from .exceptions import AttributeImmutabilityError
                raise AttributeImmutabilityError( name )
            super( cls, self ).__setattr__( name, value )

        cls.__init__ = __init__
        cls.__delattr__ = __delattr__
        cls.__setattr__ = __setattr__
        return cls

    if not __.is_absent( class_ ): return decorator( class_ )
    return decorator # No class to decorate; keyword arguments only.


@immutable
class Object:
    ''' Immutable objects. '''

    __slots__ = ( '__dict__', '_behaviors_' )

    def __repr__( self ) -> str:
        return "{fqname}( )".format( fqname = __.calculate_fqname( self ) )

Object.__doc__ = __.generate_docstring(
    Object, 'instance attributes immutability' )
