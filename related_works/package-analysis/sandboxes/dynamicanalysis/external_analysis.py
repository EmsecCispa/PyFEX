#!/usr/bin/env python3
import asyncio
import importlib
import importlib.metadata
import inspect
import os.path
import signal
import subprocess
import sys
import traceback
from contextlib import redirect_stdout, redirect_stderr
from dataclasses import dataclass, field
from typing import Optional, Set
from unittest.mock import MagicMock

PY_EXTENSION = '.py'
EXECUTION_LOG_PATH = '/execution.log'
EXECUTION_TIMEOUT_SECONDS = 10

@dataclass
class AnalysisStats:
    total_discovered: int = 0
    success: int = 0
    fail: int = 0

    def report(self):
        rate = (self.success / self.total_discovered * 100) if self.total_discovered > 0 else 0
        print(f"Discovered: {self.total_discovered} | Success: {self.success} | Fail: {self.fail} | Rate: {rate:.2f}%")

stats = AnalysisStats()

@dataclass
class Package:
    name: str
    version: Optional[str] = None
    local_path: Optional[str] = None

    def install_arg(self) -> str:
        if self.local_path: return self.local_path
        return f'{self.name}=={self.version}' if self.version else self.name

def install(package):
    arg = package.install_arg()
    try:
        subprocess.check_output((sys.executable, '-m', 'pip', 'install', '--pre', arg), stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError:
        sys.exit(1)

def module_paths_to_import(package):
    paths = []
    try:
        files = importlib.metadata.files(package.name)
        if files:
            for f in files:
                if f.suffix == PY_EXTENSION:
                    p = str(f.parent) if f.name == '__init__.py' else str(f).removesuffix(PY_EXTENSION)
                    paths.append(p.replace('/', '.'))
    except: pass
    return paths

def import_package(package):
    for p in module_paths_to_import(package):
        try: importlib.import_module(p)
        except: pass

def execute_package(package):
    for p in module_paths_to_import(package):
        try:
            module = importlib.import_module(p)
            execute_module(module)
        except: pass

def execute_module(module):
    signal.signal(signal.SIGALRM, lambda s, f: exec('raise TimeoutError()'))
    with open(EXECUTION_LOG_PATH, 'at') as log, redirect_stdout(log), redirect_stderr(log):
        try: do_execute(module)
        except: pass
    signal.signal(signal.SIGALRM, signal.SIG_DFL)

def do_execute(module):
    seen_types = set()
    instantiated_types = set()

    for _, member in inspect.getmembers(module):
        if inspect.isfunction(member) or inspect.isclass(member):
            stats.total_discovered += 1
            res = run_call(member)
            
            if res is not None:
                t = res.__class__
                if t.__module__ == module.__name__ and t not in seen_types:
                    seen_types.add(t)
                    if inspect.isclass(member): instantiated_types.add(member)
                    explore_methods(res, module.__name__, seen_types)

def run_call(obj):
    try:
        sig = inspect.signature(obj)
        kwargs = {n: (MagicMock() if p.default == p.empty else p.default) 
                  for n, p in sig.parameters.items() if p.kind not in (p.VAR_POSITIONAL, p.VAR_KEYWORD)}
        
        signal.alarm(EXECUTION_TIMEOUT_SECONDS)
        ret = obj(**kwargs)
        
        if inspect.isasyncgen(ret):
            ret = asyncio.run(lambda: [x async for x in ret]())
        elif inspect.isgenerator(ret):
            ret = list(ret)
        elif inspect.iscoroutine(ret):
            ret = asyncio.run(ret)
            
        signal.alarm(0)
        stats.success += 1
        return ret
    except:
        signal.alarm(0)
        stats.fail += 1
        return None

def explore_methods(instance, mod_name, seen_types):
    for _, m in inspect.getmembers(instance, lambda x: inspect.ismethod(x) and x.__name__ != '__init__'):
        stats.total_discovered += 1
        res = run_call(m)
        if res is not None:
            t = res.__class__
            if t.__module__ == mod_name and t not in seen_types:
                seen_types.add(t)
                explore_methods(res, mod_name, seen_types)

PHASES = {'all': [install, import_package, execute_package], 'install': [install], 
          'import': [import_package], 'execute': [execute_package]}

def main():
    args = sys.argv[1:]
    if len(args) < 2: return -1

    local_path = version = None
    if args[0] == '--local': args.pop(0); local_path = args.pop(0)
    elif args[0] == '--version': args.pop(0); version = args.pop(0)

    phase, pkg_name = args[0], args[1]
    pkg = Package(pkg_name, version, local_path)

    for proc in PHASES.get(phase, []): proc(pkg)
    
    if phase in ['all', 'execute']: stats.report()
    return 0

if __name__ == '__main__':
    sys.exit(main())