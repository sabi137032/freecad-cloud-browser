# tests/test_providers_smoke.py
# Smoke tests for all provider implementations — list_directory and upload_file.
# All external SDK calls are mocked; no real network calls or credentials needed.

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, mock_open
import pytest

from providers.base import RemoteItem


# ---------------------------------------------------------------------------
# Dropbox
# ---------------------------------------------------------------------------

class TestDropboxSmoke:
    """Smoke tests for DropboxProvider."""

    def _make_provider(self, mock_dbx):
        from providers.dropbox import DropboxProvider
        provider = DropboxProvider({"name": "test_dbx", "app_key": "fk", "app_secret": "fs"})
        provider._authenticated = True
        provider._dbx = mock_dbx
        return provider

    def test_dropbox_list_directory(self):
        """list_directory returns a list containing the mocked FileMetadata entry."""
        import dropbox as dbx_mod

        mock_dbx = MagicMock()

        # Build a realistic FileMetadata mock
        entry = MagicMock(spec=dbx_mod.files.FileMetadata)
        entry.name = "test.fcstd"
        entry.path_lower = "/test.fcstd"
        entry.size = 100
        entry.client_modified = datetime(2024, 1, 1)

        result_obj = MagicMock()
        result_obj.entries = [entry]
        result_obj.has_more = False
        mock_dbx.files_list_folder.return_value = result_obj

        provider = self._make_provider(mock_dbx)
        items = provider.list_directory("/")

        mock_dbx.files_list_folder.assert_called_once_with("")
        assert isinstance(items, list)
        assert len(items) == 1
        assert items[0].name == "test.fcstd"
        assert isinstance(items[0], RemoteItem)

    def test_dropbox_upload_file(self, tmp_path):
        """upload_file calls the chunked upload session API (start + finish)."""
        import dropbox as dbx_mod

        mock_dbx = MagicMock()

        # Set up session start mock
        session_start_result = MagicMock()
        session_start_result.session_id = "session123"
        mock_dbx.files_upload_session_start.return_value = session_start_result

        # UploadSessionCursor needs to be a real-ish object so offset comparison works
        # We patch dropbox.files.UploadSessionCursor and CommitInfo inside the module
        local_file = tmp_path / "test.fcstd"
        local_file.write_bytes(b"FreeCAD data here")  # small file, single chunk

        provider = self._make_provider(mock_dbx)

        with patch("dropbox.files.CommitInfo") as mock_commit_cls, \
             patch("dropbox.files.WriteMode") as mock_write_mode, \
             patch("dropbox.files.UploadSessionCursor") as mock_cursor_cls:

            mock_cursor_instance = MagicMock()
            mock_cursor_instance.offset = len(b"FreeCAD data here")
            mock_cursor_instance.session_id = "session123"
            mock_cursor_cls.return_value = mock_cursor_instance

            provider.upload_file(str(local_file), "/uploads")

        # finish should have been called once (small file fits in one chunk)
        mock_dbx.files_upload_session_finish.assert_called_once()


# ---------------------------------------------------------------------------
# Google Drive
# ---------------------------------------------------------------------------

class TestGoogleDriveSmoke:
    """Smoke tests for GoogleDriveProvider."""

    def _make_provider(self, mock_service):
        from providers.google_drive import GoogleDriveProvider
        provider = GoogleDriveProvider({"name": "test_gdrive", "client_id": "cid", "client_secret": "cs"})
        provider._authenticated = True
        provider._service = mock_service
        return provider

    def test_gdrive_list_directory(self):
        """list_directory returns one RemoteItem from the mocked files().list() response."""
        mock_service = MagicMock()
        mock_service.files().list().execute.return_value = {
            "files": [
                {
                    "id": "abc123",
                    "name": "part.fcstd",
                    "mimeType": "application/octet-stream",
                    "size": "512",
                    "modifiedTime": "2024-01-01T00:00:00Z",
                }
            ]
        }

        provider = self._make_provider(mock_service)
        items = provider.list_directory("root")

        assert isinstance(items, list)
        assert len(items) == 1
        assert items[0].name == "part.fcstd"
        assert items[0].size == 512
        assert isinstance(items[0], RemoteItem)

    def test_gdrive_upload_file(self, tmp_path):
        """upload_file calls files().create() on the service."""
        mock_service = MagicMock()

        local_file = tmp_path / "model.fcstd"
        local_file.write_bytes(b"drive data")

        provider = self._make_provider(mock_service)

        with patch("googleapiclient.http.MediaFileUpload"):
            provider.upload_file(str(local_file), "folder_id_123")

        mock_service.files().create.assert_called_once()
        mock_service.files().create().execute.assert_called_once()


# ---------------------------------------------------------------------------
# OneDrive
# ---------------------------------------------------------------------------

class TestOneDriveSmoke:
    """Smoke tests for OneDriveProvider."""

    def _make_provider(self, token="fake_access_token"):
        from providers.onedrive import OneDriveProvider
        provider = OneDriveProvider({
            "name": "test_onedrive",
            "client_id": "fake_client_id",
        })
        provider._authenticated = True
        provider._token = token
        provider._token_expiry = None  # prevent refresh attempt
        return provider

    def test_onedrive_list_directory(self):
        """list_directory returns one RemoteItem from the mocked Graph API response."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "value": [
                {
                    "name": "doc.fcstd",
                    "file": {},
                    "size": 200,
                    "lastModifiedDateTime": "2024-01-01T00:00:00Z",
                    "id": "item_id_1",
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()

        provider = self._make_provider()

        # requests is imported locally inside list_directory, so patch at the module level
        with patch("requests.get", return_value=mock_response) as mock_get:
            items = provider.list_directory("/")

        assert isinstance(items, list)
        assert len(items) == 1
        assert items[0].name == "doc.fcstd"
        assert isinstance(items[0], RemoteItem)
        mock_get.assert_called_once()

    def test_onedrive_upload_file(self, tmp_path):
        """upload_file (small file path) calls requests.put with a URL containing the filename."""
        local_file = tmp_path / "upload.fcstd"
        local_file.write_bytes(b"onedrive content")  # < 4 MB threshold

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        provider = self._make_provider()

        # requests is imported locally inside upload_file, so patch at the module level
        with patch("requests.put", return_value=mock_response) as mock_put:
            result = provider.upload_file(str(local_file), "parent_folder_id")

        assert result is True
        mock_put.assert_called_once()
        call_url = mock_put.call_args[0][0]
        assert "upload.fcstd" in call_url


# ---------------------------------------------------------------------------
# WebDAV
# ---------------------------------------------------------------------------

class TestWebDAVSmoke:
    """Smoke tests for WebDAVProvider."""

    def _make_provider(self, mock_client):
        from providers.webdav import WebDAVProvider
        provider = WebDAVProvider({
            "name": "test_webdav",
            "url": "https://dav.example.com/",
            "username": "user",
            "password": "pass",
        })
        provider._authenticated = True
        provider._client = mock_client
        return provider

    def test_webdav_list_directory(self):
        """list_directory returns one RemoteItem from the mocked client list response."""
        mock_client = MagicMock()
        # webdav3 with get_info=True returns list of dicts
        mock_client.list.return_value = [
            {
                "name": ".",
                "isdir": True,
                "path": "/",
                "size": None,
                "modified": None,
            },
            {
                "name": "file.fcstd",
                "isdir": False,
                "path": "/file.fcstd",
                "size": "100",
                "modified": "Mon, 01 Jan 2024 00:00:00 GMT",
            },
        ]

        provider = self._make_provider(mock_client)
        items = provider.list_directory("/")

        mock_client.list.assert_called_once()
        assert isinstance(items, list)
        # The "." entry is filtered out by provider code
        assert len(items) == 1
        assert items[0].name == "file.fcstd"
        assert isinstance(items[0], RemoteItem)

    def test_webdav_upload_file(self, tmp_path):
        """upload_file calls upload_sync on the mock client."""
        mock_client = MagicMock()
        local_file = tmp_path / "model.fcstd"
        local_file.write_bytes(b"webdav content")

        provider = self._make_provider(mock_client)
        result = provider.upload_file(str(local_file), "/remote/dir")

        assert result is True
        mock_client.upload_sync.assert_called_once()


# ---------------------------------------------------------------------------
# FTP
# ---------------------------------------------------------------------------

class TestFTPSmoke:
    """Smoke tests for FTPProvider (FTP mode, not SFTP)."""

    def _make_provider(self, mock_ftp):
        from providers.ftp import FTPProvider
        provider = FTPProvider({
            "name": "test_ftp",
            "protocol": "FTP",
            "host": "ftp.example.com",
            "username": "ftpuser",
            "password": "ftppass",
        })
        provider._authenticated = True
        provider._ftp = mock_ftp
        provider._use_sftp = False
        return provider

    def test_ftp_list_directory(self):
        """list_directory returns two RemoteItems: one file and one directory."""
        mock_ftp = MagicMock()

        # Simulate LIST output via retrlines callback pattern
        # The FTPProvider calls: self._ftp.retrlines("LIST", lines.append)
        # We simulate this by capturing the callback and calling it
        unix_file_line = "-rw-r--r-- 1 user group   50 Jan 01 00:00 file.fcstd"
        unix_dir_line  = "drwxr-xr-x 2 user group 4096 Jan 01 00:00 subdir"

        def fake_retrlines(cmd, callback):
            callback(unix_file_line)
            callback(unix_dir_line)

        mock_ftp.retrlines.side_effect = fake_retrlines

        provider = self._make_provider(mock_ftp)
        items = provider.list_directory("/")

        assert isinstance(items, list)
        # filter_freecad_files keeps dirs + .fcstd files
        assert len(items) == 2
        names = {i.name for i in items}
        assert "file.fcstd" in names
        assert "subdir" in names

    def test_ftp_upload_file(self, tmp_path):
        """upload_file calls storbinary on the FTP client."""
        mock_ftp = MagicMock()
        local_file = tmp_path / "upload.fcstd"
        local_file.write_bytes(b"ftp content")

        provider = self._make_provider(mock_ftp)
        result = provider.upload_file(str(local_file), "/remote")

        assert result is True
        mock_ftp.storbinary.assert_called_once()
        call_args = mock_ftp.storbinary.call_args[0]
        assert "upload.fcstd" in call_args[0]  # STOR command contains filename


# ---------------------------------------------------------------------------
# S3
# ---------------------------------------------------------------------------

class TestS3Smoke:
    """Smoke tests for S3Provider."""

    def _make_provider(self, mock_s3_client):
        from providers.s3 import S3Provider
        provider = S3Provider({
            "name": "test_s3",
            "access_key": "AKIAIOSFODNN7FAKE",
            "secret_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYFAKEKEY",
            "bucket": "my-test-bucket",
            "region": "us-east-1",
        })
        provider._authenticated = True
        provider._client = mock_s3_client
        return provider

    def test_s3_list_directory(self):
        """list_directory returns both a file and a folder RemoteItem via the paginator."""
        mock_client = MagicMock()

        # Mock the paginator
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator

        page = {
            "Contents": [
                {
                    "Key": "folder/file.fcstd",
                    "Size": 300,
                    "LastModified": datetime(2024, 1, 1, tzinfo=timezone.utc),
                }
            ],
            "CommonPrefixes": [
                {"Prefix": "folder/sub/"}
            ],
        }
        mock_paginator.paginate.return_value = [page]

        provider = self._make_provider(mock_client)
        items = provider.list_directory("folder/")

        mock_client.get_paginator.assert_called_once_with("list_objects_v2")
        assert isinstance(items, list)
        assert len(items) == 2

        names = {i.name for i in items}
        assert "file.fcstd" in names
        assert "sub" in names

        file_item = next(i for i in items if not i.is_dir)
        assert file_item.size == 300
        assert file_item.is_dir is False

        dir_item = next(i for i in items if i.is_dir)
        assert dir_item.is_dir is True

    def test_s3_upload_file(self, tmp_path):
        """upload_file calls upload_file on the S3 client with the correct bucket."""
        mock_client = MagicMock()
        local_file = tmp_path / "model.fcstd"
        local_file.write_bytes(b"s3 content")

        provider = self._make_provider(mock_client)
        result = provider.upload_file(str(local_file), "projects/v1")

        assert result is True
        mock_client.upload_file.assert_called_once()
        call_args = mock_client.upload_file.call_args
        assert call_args[0][1] == "my-test-bucket"
        assert "model.fcstd" in call_args[0][2]
