from datetime import datetime, timezone
from pathlib import Path
import pytest
from core.file_cache import FileCache


def test_cache_key_deterministic(cache):
    k1 = cache._cache_key("dropbox", "/a/b.fcstd")
    k2 = cache._cache_key("dropbox", "/a/b.fcstd")
    assert k1 == k2
    assert len(k1) == 20


def test_cache_key_differs_by_provider(cache):
    assert cache._cache_key("dropbox", "/x") != cache._cache_key("s3", "/x")


def test_get_local_path_creates_dir(cache):
    path = cache.get_local_path("dropbox", "/foo", "bar.fcstd")
    assert Path(path).parent.exists()


def test_is_cached_false_when_missing(cache):
    assert cache.is_cached("dropbox", "/missing/path", "file.fcstd") is False


def test_is_cached_true_when_file_exists(cache):
    path = cache.get_local_path("dropbox", "/exists", "file.fcstd")
    Path(path).write_bytes(b"x" * 10)
    assert cache.is_cached("dropbox", "/exists", "file.fcstd", remote_modified=None) is True


def test_is_cached_stale_when_remote_newer(cache):
    path = cache.get_local_path("dropbox", "/stale", "file.fcstd")
    Path(path).write_bytes(b"x" * 10)
    assert cache.is_cached("dropbox", "/stale", "file.fcstd", remote_modified="2099-01-01T00:00:00Z") is False


def test_is_cached_fresh_when_remote_older(cache):
    path = cache.get_local_path("dropbox", "/fresh", "file.fcstd")
    Path(path).write_bytes(b"x" * 10)
    assert cache.is_cached("dropbox", "/fresh", "file.fcstd", remote_modified="2000-01-01T00:00:00Z") is True


def test_is_cached_unix_timestamp(cache):
    path = cache.get_local_path("dropbox", "/unix", "file.fcstd")
    Path(path).write_bytes(b"x" * 10)
    # remote_modified="0" = Unix epoch; local file written now is newer → True
    assert cache.is_cached("dropbox", "/unix", "file.fcstd", remote_modified="0") is True


def test_invalidate_removes_file(cache):
    path = cache.get_local_path("dropbox", "/inv", "file.fcstd")
    Path(path).write_bytes(b"x" * 10)
    cache.invalidate("dropbox", "/inv", "file.fcstd")
    assert cache.is_cached("dropbox", "/inv", "file.fcstd") is False


def test_clear_provider_removes_dir(cache):
    path = cache.get_local_path("dropbox", "/prov", "file.fcstd")
    Path(path).write_bytes(b"x" * 10)
    cache.clear_provider("dropbox")
    import os
    assert not os.path.isdir(os.path.join(cache._root, "dropbox"))


def test_cache_size_bytes(cache):
    path1 = cache.get_local_path("dropbox", "/size1", "a.fcstd")
    path2 = cache.get_local_path("dropbox", "/size2", "b.fcstd")
    Path(path1).write_bytes(b"A" * 100)
    Path(path2).write_bytes(b"B" * 200)
    assert cache.cache_size_bytes() >= 300
