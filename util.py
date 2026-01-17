# pyright: ignore[reportUnusedExpression]

import sys
from datetime import datetime, timezone
import functools
from colorama import Fore, Style

class _flush_t:
    def __init__(self, content: str = "") -> None:
        self.content = content

class Lvl:
    INFO = info = Info = f"[INFO] "
    WARN = warn = Warn = f"[WARN] "
    FATAL = fatal = Fatal = f"[FATAL] "

flush = _flush_t()
endl = _flush_t(content="\n")

class TeeLogger:
    def __init__(self, *files) -> None:
        if len(files) == 0:
            files = [sys.stdout]
        self.files = files
        self.content: str = ""
        self.raise_afterward = False
    
    def __lshift__(self, other) -> 'TeeLogger':
        if isinstance(other, _flush_t):
            for f in self.files:
                f.write(f"[{datetime.now(timezone.utc).isoformat()}] ")
                f.write(self.content)
                f.write(other.content)
                f.flush()
            self.content = ""
            if self.raise_afterward:
                raise RuntimeError(self.content)
            else:
                return self
        elif isinstance(other, Lvl):
            if other == Lvl.FATAL:
                self.raise_afterward = True
        self.content += other
        return self
    
log = TeeLogger(sys.stdout, open("./app.log", "w"))

def Log(_func=None, *, logger=log):
    """Decorator factory that works with or without parentheses"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logger << Lvl.INFO << f"Function {func.__name__} called with {args}{f" and {kwargs}" if kwargs else ""}" << endl # pyright: ignore[reportUnusedExpression]
            
            try:
                result = func(*args, **kwargs)
            except Exception as e:
                logger << Lvl.FATAL << f"Function {func.__name__} raised an error: {e}" << endl # pyright: ignore[reportUnusedExpression]
                raise
            
            logger << Lvl.INFO << f"Function {func.__name__} returned: {result}" << endl # pyright: ignore[reportUnusedExpression]
            return result
        return wrapper
    
    # Handle both @Log and @Log() syntax
    if _func is None:
        # Called with parentheses or with arguments: @Log() or @Log(logger=...)
        return decorator
    else:
        # Called without parentheses: @Log
        return decorator(_func)