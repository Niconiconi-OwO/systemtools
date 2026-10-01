# -*- coding: utf-8 -*-
"""Unit tests for VFS utilities (local and SMB/NFS path operations)."""

import io
import os
import tarfile
import pytest

from resources.lib.common.vfs_utils import (
    VfsFileStream,
    get_filename_from_path,
    is_vfs_path,
    open_tar_archive,
    vfs_delete_file,
    vfs_file_exists,
    vfs_file_size,
)
import xbmcvfs
MockVfsFile = xbmcvfs.File


def test_is_vfs_path():
    assert is_vfs_path("smb://192.168.1.100/share/file.tar") is True
    assert is_vfs_path("nfs://192.168.1.100/export/file.tar") is True
    assert is_vfs_path("special://home/addons/file.tar") is True
    assert is_vfs_path("/storage/.update/file.tar") is False
    assert is_vfs_path(r"C:\Users\User\file.tar") is False
    assert is_vfs_path("") is False
    assert is_vfs_path(None) is False


def test_get_filename_from_path():
    assert get_filename_from_path("smb://192.168.1.100/share/test_file.tar") == "test_file.tar"
    assert get_filename_from_path("smb://user:pass@nas/share/my%20file.tar") == "my file.tar"
    assert get_filename_from_path("nfs://server/volume1/CoreELEC.tar?param=1#anchor") == "CoreELEC.tar"
    assert get_filename_from_path("/storage/.update/update.tar") == "update.tar"
    assert get_filename_from_path(r"C:\Downloads\ce.tar") == "ce.tar"
    assert get_filename_from_path("") == ""
    assert get_filename_from_path(None) == ""


def test_vfs_file_exists_and_size(tmp_path):
    local_file = str(tmp_path / "test.bin")
    data = b"HELLO_VFS_TEST_DATA" * 50
    with open(local_file, "wb") as f:
        f.write(data)

    # Local file checks
    assert vfs_file_exists(local_file) is True
    assert vfs_file_size(local_file) == len(data)
    assert vfs_file_exists(str(tmp_path / "nonexistent.bin")) is False

    # Mocked VFS URL checks
    smb_url = "smb://nas/share/test.bin"
    MockVfsFile.register_url(smb_url, local_file)
    try:
        assert vfs_file_exists(smb_url) is True
        assert vfs_file_size(smb_url) == len(data)
        assert vfs_file_exists("smb://nas/share/missing.bin") is False
    finally:
        MockVfsFile.clear_urls()


def test_vfs_delete_file(tmp_path):
    # Test local file delete
    local_file = str(tmp_path / "to_delete.txt")
    with open(local_file, "w") as f:
        f.write("delete me")
    assert os.path.exists(local_file)
    assert vfs_delete_file(local_file) is True
    assert not os.path.exists(local_file)

    # Test VFS URL delete
    smb_file = str(tmp_path / "smb_del.txt")
    with open(smb_file, "w") as f:
        f.write("delete smb")
    smb_url = "smb://nas/share/smb_del.txt"
    MockVfsFile.register_url(smb_url, smb_file)
    try:
        assert vfs_delete_file(smb_url) is True
        assert smb_url not in MockVfsFile._url_map
    finally:
        MockVfsFile.clear_urls()


def test_vfs_file_stream_io(tmp_path):
    raw_content = b"0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ" * 10
    local_file = str(tmp_path / "stream_test.bin")
    with open(local_file, "wb") as f:
        f.write(raw_content)

    smb_url = "smb://nas/share/stream_test.bin"
    MockVfsFile.register_url(smb_url, local_file)
    try:
        stream = VfsFileStream(smb_url)
        assert stream.readable() is True
        assert stream.seekable() is True
        assert stream.writable() is False
        assert stream.tell() == 0

        # Read 10 bytes
        chunk1 = stream.read(10)
        assert chunk1 == raw_content[:10]
        assert stream.tell() == 10

        # Seek forward (CUR)
        stream.seek(10, io.SEEK_CUR)
        assert stream.tell() == 20

        # Read into buffer
        buf = bytearray(5)
        n = stream.readinto(buf)
        assert n == 5
        assert buf == raw_content[20:25]
        assert stream.tell() == 25

        # Seek from end (END)
        stream.seek(-5, io.SEEK_END)
        assert stream.tell() == len(raw_content) - 5
        assert stream.read(5) == raw_content[-5:]

        # Seek to start (SET)
        stream.seek(0, io.SEEK_SET)
        assert stream.tell() == 0
        all_data = stream.read()
        assert all_data == raw_content

        stream.close()
    finally:
        MockVfsFile.clear_urls()


def test_open_tar_archive_vfs(tmp_path):
    local_tar = str(tmp_path / "test_archive.tar")
    file1_data = b"KERNEL_TEST_DATA" * 100
    file2_data = b"SYSTEM_TEST_DATA" * 200

    with tarfile.open(local_tar, "w") as tar:
        t1 = tarfile.TarInfo("KERNEL")
        t1.size = len(file1_data)
        tar.addfile(t1, io.BytesIO(file1_data))

        t2 = tarfile.TarInfo("SYSTEM")
        t2.size = len(file2_data)
        tar.addfile(t2, io.BytesIO(file2_data))

    smb_url = "smb://192.168.1.50/share/test_archive.tar"
    MockVfsFile.register_url(smb_url, local_tar)
    try:
        with open_tar_archive(smb_url, buffer_size=4096) as archive:
            members = [m.name for m in archive.getmembers()]
            assert "KERNEL" in members
            assert "SYSTEM" in members

            f1 = archive.extractfile("KERNEL").read()
            assert f1 == file1_data

            f2 = archive.extractfile("SYSTEM").read()
            assert f2 == file2_data
    finally:
        MockVfsFile.clear_urls()
