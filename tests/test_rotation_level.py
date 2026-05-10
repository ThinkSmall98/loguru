import os
import pathlib
import tempfile

import pytest

from loguru import logger

from .conftest import check_dir


@pytest.fixture
def tmp_path_local(reset_logger):
    with tempfile.TemporaryDirectory(dir=".") as tmp_path:
        yield pathlib.Path(tmp_path)
        logger.remove()


def test_rotation_level_basic(tmp_path_local):
    logger.add(tmp_path_local / "test.log", rotation="level", rotation_level="ERROR", format="{message}")
    
    logger.info("info message")
    logger.warning("warning message")
    
    files = list(tmp_path_local.iterdir())
    assert len(files) == 1
    assert files[0].name == "test.log"
    assert files[0].read_text() == "info message\nwarning message\n"
    
    logger.error("error message")
    
    files = sorted(tmp_path_local.iterdir())
    assert len(files) == 2
    
    rotated_file = [f for f in files if f.name.startswith("test.2")][0]
    current_file = [f for f in files if f.name == "test.log"][0]
    
    assert rotated_file.read_text() == "info message\nwarning message\nerror message\n"
    assert current_file.read_text() == ""


def test_rotation_level_default(tmp_path_local):
    logger.add(tmp_path_local / "test.log", rotation="level", format="{message}")
    
    logger.info("info message")
    logger.warning("warning message")
    
    files = list(tmp_path_local.iterdir())
    assert len(files) == 1
    assert files[0].name == "test.log"
    assert files[0].read_text() == "info message\nwarning message\n"
    
    logger.error("error message")
    
    files = sorted(tmp_path_local.iterdir())
    assert len(files) == 2
    
    rotated_file = [f for f in files if f.name.startswith("test.2")][0]
    current_file = [f for f in files if f.name == "test.log"][0]
    
    assert rotated_file.read_text() == "info message\nwarning message\nerror message\n"
    assert current_file.read_text() == ""


def test_rotation_level_integer(tmp_path_local):
    logger.add(tmp_path_local / "test.log", rotation="level", rotation_level=20, format="{message}")
    
    logger.debug("debug message")
    
    files = list(tmp_path_local.iterdir())
    assert len(files) == 1
    assert files[0].name == "test.log"
    assert files[0].read_text() == "debug message\n"
    
    logger.info("info message")
    
    files = sorted(tmp_path_local.iterdir())
    assert len(files) == 2
    
    rotated_file = [f for f in files if f.name.startswith("test.2")][0]
    current_file = [f for f in files if f.name == "test.log"][0]
    
    assert rotated_file.read_text() == "debug message\ninfo message\n"
    assert current_file.read_text() == ""


def test_rotation_level_triggering_record_is_last(tmp_path_local):
    logger.add(tmp_path_local / "test.log", rotation="level", rotation_level="ERROR", format="{message}")
    
    logger.info("info 1")
    logger.info("info 2")
    logger.error("error 1")
    logger.info("info 3")
    
    rotated_file = None
    for file in os.listdir(tmp_path_local):
        if file.startswith("test.2"):
            rotated_file = file
            break
    
    assert rotated_file is not None
    
    with open(tmp_path_local / rotated_file) as f:
        content = f.read()
    
    assert content == "info 1\ninfo 2\nerror 1\n"
    
    with open(tmp_path_local / "test.log") as f:
        content = f.read()
    
    assert content == "info 3\n"


def test_rotation_level_combined_with_size(tmp_path_local):
    logger.add(tmp_path_local / "test.log", rotation=["100 B", "level"], rotation_level="ERROR", format="{message}")
    
    logger.info("small")
    
    files = list(tmp_path_local.iterdir())
    assert len(files) == 1
    assert files[0].name == "test.log"
    assert files[0].read_text() == "small\n"
    
    logger.error("error triggers rotation")
    
    files = sorted(tmp_path_local.iterdir())
    assert len(files) == 2
    
    rotated_file = [f for f in files if f.name.startswith("test.2")][0]
    current_file = [f for f in files if f.name == "test.log"][0]
    
    assert rotated_file.read_text() == "small\nerror triggers rotation\n"
    assert current_file.read_text() == ""
    
    long_message = "x" * 200
    logger.info(long_message)
    
    files = sorted(tmp_path_local.iterdir())
    assert len(files) == 3
    
    rotated_files = [f for f in files if f.name.startswith("test.2")]
    current_file = [f for f in files if f.name == "test.log"][0]
    
    assert len(rotated_files) == 2
    assert rotated_files[0].read_text() == "small\nerror triggers rotation\n"
    assert rotated_files[1].read_text() == ""
    assert current_file.read_text() == f"{long_message}\n"


def test_rotation_level_combined_deduplication(tmp_path_local):
    logger.add(tmp_path_local / "test.log", rotation=["50 B", "level"], rotation_level="ERROR", format="{message}")
    
    long_error = "x" * 100
    logger.error(long_error)
    
    files = sorted(tmp_path_local.iterdir())
    rotated_count = sum(1 for f in files if f.name.startswith("test.2"))
    
    assert len(files) == 2
    assert rotated_count == 1
    
    rotated_file = [f for f in files if f.name.startswith("test.2")][0]
    current_file = [f for f in files if f.name == "test.log"][0]
    
    assert rotated_file.read_text() == f"{long_error}\n"
    assert current_file.read_text() == ""


def test_rotation_level_multiple_triggers(tmp_path_local):
    logger.add(tmp_path_local / "test.log", rotation="level", rotation_level="ERROR", format="{message}")
    
    logger.info("info 1")
    logger.error("error 1")
    logger.info("info 2")
    logger.error("error 2")
    logger.info("info 3")
    
    files = sorted([f for f in os.listdir(tmp_path_local) if f.startswith("test.")])
    
    assert len(files) == 3
    
    with open(tmp_path_local / files[0]) as f:
        content = f.read()
    assert content == "info 1\nerror 1\n"
    
    with open(tmp_path_local / files[1]) as f:
        content = f.read()
    assert content == "info 2\nerror 2\n"
    
    with open(tmp_path_local / files[2]) as f:
        content = f.read()
    assert content == "info 3\n"


def test_rotation_level_critical(tmp_path_local):
    logger.add(tmp_path_local / "test.log", rotation="level", rotation_level="CRITICAL", format="{message}")
    
    logger.error("error message")
    logger.warning("warning message")
    
    files = list(tmp_path_local.iterdir())
    assert len(files) == 1
    assert files[0].name == "test.log"
    assert files[0].read_text() == "error message\nwarning message\n"
    
    logger.critical("critical message")
    
    files = sorted(tmp_path_local.iterdir())
    assert len(files) == 2
    
    rotated_file = [f for f in files if f.name.startswith("test.2")][0]
    current_file = [f for f in files if f.name == "test.log"][0]
    
    assert rotated_file.read_text() == "error message\nwarning message\ncritical message\n"
    assert current_file.read_text() == ""


def test_rotation_level_case_insensitive(tmp_path_local):
    logger.add(tmp_path_local / "test.log", rotation="level", rotation_level="error", format="{message}")
    
    logger.info("info message")
    logger.error("error message")
    
    files = sorted(tmp_path_local.iterdir())
    assert len(files) == 2
    
    rotated_file = [f for f in files if f.name.startswith("test.2")][0]
    current_file = [f for f in files if f.name == "test.log"][0]
    
    assert rotated_file.read_text() == "info message\nerror message\n"
    assert current_file.read_text() == ""


def test_rotation_level_invalid_string(tmp_path_local):
    with pytest.raises(ValueError, match="Cannot parse rotation_level"):
        logger.add(tmp_path_local / "test.log", rotation="level", rotation_level="INVALID")


def test_rotation_level_invalid_type(tmp_path_local):
    with pytest.raises(TypeError, match="Cannot infer rotation_level"):
        logger.add(tmp_path_local / "test.log", rotation="level", rotation_level=[])
