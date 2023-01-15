from Untested.postgresql import PostgresBackend
from sqlite import SQLiteBackend

# list of available storage backends
BACKENDS = {
    'postgresql': PostgresBackend,
    'sqlite': SQLiteBackend
}

def get_storage(backend: str, *args, **kwargs):
    """Returns an instance of the specified storage backend"""
    if backend not in BACKENDS:
        raise ValueError(f"Invalid storage backend: {backend}")
    return BACKENDS[backend](*args, **kwargs)
