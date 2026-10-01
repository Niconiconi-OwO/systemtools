# -*- coding: utf-8 -*-
"""Unit tests for Kodi Performance Optimizer tool."""

import os
import sqlite3
import xml.etree.ElementTree as ET

from resources.lib.tools.kodi_optimizer import (
    CUSTOM_INDEXES,
    KodiOptimizerTool,
    apply_custom_indexes,
    backup_file,
    drop_custom_indexes,
    format_size,
    get_database_files,
)


def create_dummy_db(db_path: str):
    """Helper to create a test SQLite database."""
    conn = sqlite3.connect(db_path, isolation_level=None)
    cur = conn.cursor()
    cur.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, title TEXT);")
    cur.execute("INSERT INTO test (title) VALUES ('Movie 1');")
    # Set default journal_mode to delete
    cur.execute("PRAGMA journal_mode = DELETE;")
    cur.execute("PRAGMA synchronous = FULL;")
    conn.close()


def test_optimize_databases(tmp_path):
    userdata = str(tmp_path / "userdata")
    db_dir = os.path.join(userdata, "Database")
    os.makedirs(db_dir, exist_ok=True)

    db1 = os.path.join(db_dir, "MyVideos119.db")
    db2 = os.path.join(db_dir, "Textures13.db")
    create_dummy_db(db1)
    create_dummy_db(db2)

    tool = KodiOptimizerTool(userdata_path=userdata)

    # Run database optimizations
    count = tool.optimize_databases()
    assert count == 2

    # Verify backups exist
    assert os.path.exists(f"{db1}.bak")
    assert os.path.exists(f"{db2}.bak")

    # Verify WAL mode on db1
    conn = sqlite3.connect(db1)
    cur = conn.cursor()
    cur.execute("PRAGMA journal_mode;")
    j_mode = cur.fetchone()[0]
    conn.close()

    assert j_mode.lower() == "wal"


def test_optimize_advancedsettings(tmp_path):
    userdata = str(tmp_path / "userdata")
    os.makedirs(userdata, exist_ok=True)

    tool = KodiOptimizerTool(userdata_path=userdata)
    tool.optimize_advancedsettings()

    as_path = os.path.join(userdata, "advancedsettings.xml")
    assert os.path.exists(as_path)

    tree = ET.parse(as_path)
    root = tree.getroot()
    assert root.tag == "advancedsettings"

    # Verify <gui> settings
    gui = root.find("gui")
    assert gui is not None
    assert gui.findtext("asynctextureupload") == "false"
    assert gui.findtext("minifiedmipmapping") == "false"
    assert gui.findtext("algorithmdirtyregions") == "2"
    assert gui.findtext("imageres") == "720"
    assert gui.findtext("fanartres") == "1080"

    # Verify <videodatabase> settings
    vdb = root.find("videodatabase")
    assert vdb is not None
    assert vdb.findtext("cache_size") == "-32768"


def test_get_status_report(tmp_path):
    userdata = str(tmp_path / "userdata")
    db_dir = os.path.join(userdata, "Database")
    os.makedirs(db_dir, exist_ok=True)

    db_file = os.path.join(db_dir, "MyVideos119.db")
    create_dummy_db(db_file)

    tool = KodiOptimizerTool(userdata_path=userdata)
    tool.optimize_databases()
    tool.optimize_advancedsettings()

    report = tool.get_status_report()
    assert "MyVideos119.db" in report
    assert "WAL:" in report
    assert "asynctextureupload" in report
    assert "algorithmdirtyregions" in report


def test_flush_wal_databases(tmp_path):
    userdata = str(tmp_path / "userdata")
    db_dir = os.path.join(userdata, "Database")
    os.makedirs(db_dir, exist_ok=True)

    db_path = os.path.join(db_dir, "Textures13.db")
    # Simulate Kodi holding an open connection to the database
    kodi_conn = sqlite3.connect(db_path)
    kodi_conn.execute("PRAGMA journal_mode = WAL;")
    kodi_conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, data TEXT);")
    kodi_conn.commit()
    for i in range(100):
        kodi_conn.execute("INSERT INTO test (data) VALUES (?);", (f"some string {i}" * 50,))
    kodi_conn.commit()

    wal_path = f"{db_path}-wal"
    assert os.path.exists(wal_path)
    wal_size_before = os.path.getsize(wal_path)
    assert wal_size_before > 0

    tool = KodiOptimizerTool(userdata_path=userdata)
    processed_count, freed_bytes = tool.flush_wal_databases()

    assert processed_count == 1
    assert freed_bytes >= wal_size_before
    assert os.path.getsize(wal_path) == 0

    kodi_conn.close()


def test_restore_backups(tmp_path):
    userdata = str(tmp_path / "userdata")
    db_dir = os.path.join(userdata, "Database")
    os.makedirs(db_dir, exist_ok=True)

    db_file = os.path.join(db_dir, "MyVideos119.db")
    create_dummy_db(db_file)

    # Create an initial advancedsettings.xml so a .bak is produced during optimization
    as_file = os.path.join(userdata, "advancedsettings.xml")
    with open(as_file, "w", encoding="utf-8") as f:
        f.write("<advancedsettings><gui><imageres>1080</imageres></gui></advancedsettings>")

    tool = KodiOptimizerTool(userdata_path=userdata)
    tool.optimize_databases()
    tool.optimize_advancedsettings()

    # Now restore from backup
    restored = tool.restore_backups()
    assert restored >= 2  # db and advancedsettings


def test_restore_backups_cleans_wal_and_shm(tmp_path):
    userdata = str(tmp_path / "userdata")
    db_dir = os.path.join(userdata, "Database")
    os.makedirs(db_dir, exist_ok=True)

    db_file = os.path.join(db_dir, "MyVideos119.db")
    create_dummy_db(db_file)

    tool = KodiOptimizerTool(userdata_path=userdata)
    tool.optimize_databases()

    # Simulate subsequent writes creating .db-wal and .db-shm files
    wal_file = f"{db_file}-wal"
    shm_file = f"{db_file}-shm"
    with open(wal_file, "wb") as f:
        f.write(b"dummy wal content")
    with open(shm_file, "wb") as f:
        f.write(b"dummy shm content")

    assert os.path.exists(wal_file)
    assert os.path.exists(shm_file)

    # Restore from backup
    restored = tool.restore_backups()
    assert restored >= 1

    # Both wal and shm files must be removed to prevent SQLite corruption
    assert not os.path.exists(wal_file)
    assert not os.path.exists(shm_file)

    # Verify database can be queried normally
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    cur.execute("SELECT * FROM test;")
    rows = cur.fetchall()
    conn.close()
    assert len(rows) == 1


def test_restore_backups_when_advancedsettings_did_not_exist(tmp_path):
    userdata = str(tmp_path / "userdata")
    os.makedirs(userdata, exist_ok=True)

    as_file = os.path.join(userdata, "advancedsettings.xml")
    assert not os.path.exists(as_file)

    tool = KodiOptimizerTool(userdata_path=userdata)
    # Optimization creates advancedsettings.xml when it didn't exist before
    tool.optimize_advancedsettings()
    assert os.path.exists(as_file)

    # Restore from backup should restore to pre-optimization state (file deleted)
    restored = tool.restore_backups()
    assert restored >= 1
    assert not os.path.exists(as_file)


def test_format_size():
    assert format_size(500) == "500 B"
    assert format_size(1024) == "1.0 KB"
    assert format_size(1048576) == "1.0 MB"
    assert format_size(1073741824) == "1.00 GB"


def test_flush_wal_empty_dir(tmp_path):
    userdata = str(tmp_path / "userdata")
    tool = KodiOptimizerTool(userdata_path=userdata)
    count, freed = tool.flush_wal_databases()
    assert count == 0
    assert freed == 0


def test_status_report_wal_backlog(tmp_path, monkeypatch):
    userdata = str(tmp_path / "userdata")
    db_dir = os.path.join(userdata, "Database")
    os.makedirs(db_dir, exist_ok=True)

    db_file = os.path.join(db_dir, "Textures13.db")
    create_dummy_db(db_file)
    tool = KodiOptimizerTool(userdata_path=userdata)
    tool.optimize_databases()

    # Mock getsize for wal file to simulate > 16MB
    orig_getsize = os.path.getsize

    def fake_getsize(path):
        if str(path).endswith("-wal"):
            return 20 * 1024 * 1024
        return orig_getsize(path)

    monkeypatch.setattr(os.path, "getsize", fake_getsize)
    monkeypatch.setattr(os.path, "exists", lambda p: True if str(p).endswith("-wal") else os.path.lexists(p))

    report = tool.get_status_report()
    assert "WAL Backlog" in report


def test_apply_and_drop_custom_indexes():
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    cur.execute("CREATE TABLE files (idFile INT, playCount INT, dateAdded TEXT);")
    cur.execute("CREATE TABLE art (media_type TEXT, media_id INT, type TEXT, url TEXT);")
    cur.execute("CREATE TABLE bookmark (type INT, timeInSeconds REAL, idFile INT);")
    cur.execute("CREATE TABLE videoversion (idMedia INT, media_type TEXT, itemType INT, idFile INT);")

    # Apply indexes
    applied = apply_custom_indexes(conn)
    assert applied == 4

    cur.execute("SELECT name FROM sqlite_master WHERE type='index';")
    idx_names = {r[0] for r in cur.fetchall()}
    for _, idx_name, _ in CUSTOM_INDEXES:
        assert idx_name in idx_names

    # Drop indexes
    dropped = drop_custom_indexes(conn)
    assert dropped == 4

    cur.execute("SELECT name FROM sqlite_master WHERE type='index';")
    remaining_idxs = {r[0] for r in cur.fetchall()}
    for _, idx_name, _ in CUSTOM_INDEXES:
        assert idx_name not in remaining_idxs

    conn.close()


def test_optimize_databases_creates_indexes_and_vacuum(tmp_path):
    userdata = str(tmp_path / "userdata")
    db_dir = os.path.join(userdata, "Database")
    os.makedirs(db_dir, exist_ok=True)

    db_path = os.path.join(db_dir, "MyVideos131.db")
    conn = sqlite3.connect(db_path, isolation_level=None)
    cur = conn.cursor()
    cur.execute("PRAGMA page_size = 2048;")
    cur.execute("CREATE TABLE files (idFile INT PRIMARY KEY, playCount INT, dateAdded TEXT);")
    cur.execute("CREATE TABLE art (media_type TEXT, media_id INT, type TEXT, url TEXT);")
    for i in range(50):
        cur.execute("INSERT INTO files VALUES (?, ?, ?);", (i, None, f"2026-10-0{i%9+1}"))
    # Delete some rows to create freelist space
    cur.execute("DELETE FROM files WHERE idFile > 25;")
    conn.close()

    tool = KodiOptimizerTool(userdata_path=userdata)
    count = tool.optimize_databases()
    assert count == 1

    # Verify page size aligned to 4096
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("PRAGMA page_size;")
    assert cur.fetchone()[0] == 4096

    # Verify custom index was created
    cur.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_files_unwatched_recent';")
    assert cur.fetchone() is not None

    # Verify freelist was compacted
    cur.execute("PRAGMA freelist_count;")
    assert cur.fetchone()[0] == 0

    # Verify ANALYZE populated sqlite_stat1
    cur.execute("SELECT COUNT(*) FROM sqlite_stat1 WHERE tbl='files';")
    assert cur.fetchone()[0] >= 1

    conn.close()

    # Verify status report displays index active
    report = tool.get_status_report()
    assert "Indexes: Active" in report

    # Test lossless revert of custom indexes
    db_count, dropped_count = tool.revert_custom_indexes()
    assert db_count == 1
    assert dropped_count >= 1

    # Verify library data remains intact
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM files;")
    assert cur.fetchone()[0] == 26
    cur.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_files_unwatched_recent';")
    assert cur.fetchone() is None
    conn.close()


def test_backup_checkpoints_wal_before_copy(tmp_path):
    db_path = str(tmp_path / "test_wal.db")
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("CREATE TABLE items (id INT, val TEXT);")
    conn.execute("INSERT INTO items VALUES (1, 'persisted');")
    conn.commit()

    # Insert more items in WAL without manual checkpoint
    conn.execute("INSERT INTO items VALUES (2, 'in_wal');")
    conn.commit()

    wal_file = f"{db_path}-wal"
    assert os.path.exists(wal_file)

    # Perform backup
    bak_path = backup_file(db_path)
    assert os.path.exists(bak_path)

    conn.close()

    # Directly inspect backup file without wal
    bak_conn = sqlite3.connect(bak_path)
    bak_cur = bak_conn.cursor()
    bak_cur.execute("SELECT val FROM items;")
    rows = [r[0] for r in bak_cur.fetchall()]
    bak_conn.close()

    # The backed up db must contain both rows because wal was checkpointed before copy
    assert "persisted" in rows
    assert "in_wal" in rows


def test_action_revert_indexes(tmp_path, monkeypatch):
    userdata = str(tmp_path / "userdata")
    db_dir = os.path.join(userdata, "Database")
    os.makedirs(db_dir, exist_ok=True)
    db_path = os.path.join(db_dir, "MyVideos131.db")
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.execute("CREATE TABLE files (idFile INT, playCount INT, dateAdded TEXT);")
    conn.close()

    tool = KodiOptimizerTool(userdata_path=userdata)
    tool.optimize_databases()

    # Case 1: user confirms yesno dialog -> revert executed
    monkeypatch.setattr("resources.lib.tools.kodi_optimizer.dialog_yesno", lambda t, m: True)
    notifs = []
    monkeypatch.setattr("resources.lib.tools.kodi_optimizer.show_notification", lambda t, m: notifs.append(m))
    tool._action_revert_indexes("Test")
    assert len(notifs) == 1
    assert "Reverted" in notifs[0]

    # Case 2: revert again when no custom indexes exist
    notifs.clear()
    tool._action_revert_indexes("Test")
    assert len(notifs) == 1
    assert "No custom indexes found" in notifs[0]

    # Case 3: user clicks No in dialog_yesno
    monkeypatch.setattr("resources.lib.tools.kodi_optimizer.dialog_yesno", lambda t, m: False)
    notifs.clear()
    tool._action_revert_indexes("Test")
    assert len(notifs) == 0


def test_run_menu_dispatch(tmp_path, monkeypatch):
    userdata = str(tmp_path / "userdata")
    tool = KodiOptimizerTool(userdata_path=userdata)

    called = []
    monkeypatch.setattr("resources.lib.tools.kodi_optimizer.dialog_select", lambda t, opts: 3)
    monkeypatch.setattr(tool, "_action_revert_indexes", lambda t: called.append("revert"))
    tool.run({})
    assert called == ["revert"]



