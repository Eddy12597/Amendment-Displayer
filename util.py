import sys
from datetime import datetime, timezone
import functools

class _endl_t:
    def __init__(self) -> None:
        self.id = 67

class Lvl:
    INFO = info = "[INFO] "
    WARN = warn = "[WARN] "
    FATAL = fatal = "[FATAL] "
endl = _endl_t()

class TeeLogger:
    def __init__(self, *files) -> None:
        if len(files) == 0:
            files = [sys.stdout]
        self.files = files
        self.content: str = ""
        self.raise_afterward = False
    
    def __lshift__(self, other) -> 'TeeLogger':
        if isinstance(other, _endl_t):
            for f in self.files:
                f.write(f"[{datetime.now(timezone.utc).isoformat()}] ")
                f.write(self.content)
                f.write("\n")
                f.flush()
            self.content = ""
            if self.raise_afterward:
                raise RuntimeError(self.content)
            else:
                return self
        elif other == Lvl.FATAL:
            self.raise_afterward = True
        self.content += other
        return self
    
log = TeeLogger(sys.stdout, open("./app.log", "w"))

def Log(_func=None, *, logger=log):
    """Decorator factory that works with or without parentheses"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logger << Lvl.INFO << f"Function {func.__name__} called with {args} and {kwargs}" << endl
            
            result = func(*args, **kwargs)
            
            logger << Lvl.INFO << f"Function {func.__name__} returned: {result}" << endl
            return result
        return wrapper
    
    # Handle both @Log and @Log() syntax
    if _func is None:
        # Called with parentheses or with arguments: @Log() or @Log(logger=...)
        return decorator
    else:
        # Called without parentheses: @Log
        return decorator(_func)