# -*- coding: utf-8 -*-
"""Unit tests for DiskBenchmarkTool."""

import os
from unittest.mock import MagicMock
from resources.lib.tools.disk_benchmark import DiskBenchmarkTool


def test_sequential_write_and_read(tmp_path):
    tool = DiskBenchmarkTool()
    bench_file = os.path.join(str(tmp_path), "test_bench.tmp")
    mock_dp = MagicMock()
    mock_dp.is_canceled.return_value = False

    # Test sequential write (2 MB for quick test)
    write_speed = tool._test_sequential_write(bench_file, size_mb=2, dp=mock_dp)
    assert write_speed > 0
    assert os.path.exists(bench_file)
    assert os.path.getsize(bench_file) == 2 * 1024 * 1024

    # Test sequential read
    read_speed = tool._test_sequential_read(bench_file, dp=mock_dp)
    assert read_speed > 0

    # Test 4k random write (50 ops)
    iops_w, mbs_w = tool._test_4k_random_write(bench_file, size_mb=2, dp=mock_dp, ops=50)
    assert iops_w > 0
    assert mbs_w > 0

    # Test 4k random read (50 ops)
    iops_r, mbs_r = tool._test_4k_random_read(bench_file, size_mb=2, dp=mock_dp, ops=50)
    assert iops_r > 0
    assert mbs_r > 0

    # Test cleanup
    tool._cleanup_temp_file(bench_file)
    assert not os.path.exists(bench_file)


def test_flush_and_evict_cache(tmp_path):
    tool = DiskBenchmarkTool()
    dummy_file = os.path.join(str(tmp_path), "cache_test.tmp")
    with open(dummy_file, "wb") as f:
        f.write(b"DATA" * 1024)
    tool._flush_and_evict_cache(dummy_file)
    assert os.path.exists(dummy_file)
    os.remove(dummy_file)


def test_disk_benchmark_cancellation_and_edge_cases(tmp_path):
    tool = DiskBenchmarkTool()
    bench_file = os.path.join(str(tmp_path), "test_cancel.tmp")
    mock_dp = MagicMock()
    mock_dp.is_canceled.return_value = True

    # Sequential write canceled immediately
    write_speed = tool._test_sequential_write(bench_file, size_mb=2, dp=mock_dp)
    assert write_speed >= 0

    # 4k random write with 0 size
    iops_w, mbs_w = tool._test_4k_random_write(bench_file, size_mb=0, dp=mock_dp)
    assert iops_w == 0.0 and mbs_w == 0.0

    # 4k random read with 0 size
    iops_r, mbs_r = tool._test_4k_random_read(bench_file, size_mb=0, dp=mock_dp)
    assert iops_r == 0.0 and mbs_r == 0.0

    tool._cleanup_temp_file(bench_file)
