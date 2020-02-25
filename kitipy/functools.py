import functools
from typing import Callable, List, TypeVar

T = TypeVar('T')

def pipe(nullary_fn: Callable[[], T], unary_fns: List[Callable[[T], T]]) -> T:
    return functools.reduce(lambda out, fn: fn(out), unary_fns, nullary_fn())
