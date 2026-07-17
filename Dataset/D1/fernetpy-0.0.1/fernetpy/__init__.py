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


''' Immutable data structures. '''


from . import __
from . import qaliases
# --- BEGIN: Injected by Copier ---
from . import exceptions
# --- END: Injected by Copier ---

from .classes import *
from .dictionaries import *
from .installers import *
from .modules import *
from .namespaces import *
from .objects import *
from .sequences import *


__version__ = '3.0'


_attribute_visibility_includes_ = frozenset( ( '__version__', ) )
__.reclassify_modules( __name__, recursive = True )
