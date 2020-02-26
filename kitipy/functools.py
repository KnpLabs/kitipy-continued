import functools
from typing import Callable, TypeVar

T = TypeVar('T')

def pipe(nullary_fn: Callable[[], T], *unary_fns: Callable[[T], T]) -> T:
    return functools.reduce(lambda out, fn: fn(out), unary_fns, nullary_fn())
