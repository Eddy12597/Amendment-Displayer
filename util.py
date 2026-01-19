# pyright: ignore[reportUnusedExpression]

import sys
from datetime import datetime, timezone
import functools
from colorama import Fore, Style
import html2text

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


# Similarity
from fuzzywuzzy import fuzz
from fuzzywuzzy import process

def similarity(str1: str, str2: str) -> float:
    def jaccard_similarity(str1, str2):
        set1 = set(str1.split())
        set2 = set(str2.split())
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        return intersection / union if union != 0 else 0
    return (jaccard_similarity(str1, str2) + fuzz.ratio(str1, str2))/2


def html_to_text(html_body: str) -> str:
    h = html2text.HTML2Text()
    h.ignore_links = True
    h.ignore_images = True
    h.ignore_tables = False
    h.body_width = 0  # no hard wrapping

    return h.handle(html_body).strip()