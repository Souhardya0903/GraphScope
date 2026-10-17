"""Deliberately dynamic call: the extractor must retain uncertainty at this site."""


def dispatch(handlers: object, event_name: str) -> object:
    return getattr(handlers, event_name)()
