import datetime
import os
import pathlib
import tempfile
import threading
import time

import pytest

from loguru import logger


@pytest.fixture(autouse=True)
def reset_logger():
    import loguru
    import loguru._logger

    def reset():
        loguru.logger.remove()
        loguru.logger.__init__(
            loguru._logger.Core(), None, 0, False, False, False, False, True, [], {}
        )
        loguru._logger.context.set({})

    reset()
    yield
    reset()


@pytest.fixture
def tmp_path_local(reset_logger):
    with tempfile.TemporaryDirectory(dir=".") as tmp_path:
        yield pathlib.Path(tmp_path)
        logger.remove()


def check_dir(dir, *, files=None, size=None):
    actual_files = set(dir.iterdir())
    seen = set()
    if size is not None:
        assert len(actual_files) == size
    if files is not None:
        assert len(actual_files) == len(files)
        for name, content in files:
            filepath = dir / name
            assert filepath in actual_files
            assert filepath not in seen
            if content is not None:
                assert filepath.read_text() == content
            seen.add(filepath)


class TestLevelRotationBasic:
    def test_rotation_level_string_does_not_crash(self, tmp_path_local):
        i = logger.add(tmp_path_local / "test.log", rotation="level", format="{message}")
        logger.debug("hello")
        logger.remove(i)

    def test_rotation_level_default_threshold_is_40(self, tmp_path_local):
        i = logger.add(tmp_path_local / "test.log", rotation="level", format="{message}")
        logger.debug("msg1")
        logger.info("msg2")
        logger.warning("msg3")
        logger.error("msg4")
        logger.debug("msg5")
        logger.remove(i)

        files = sorted(tmp_path_local.iterdir())
        assert len(files) == 2

        rotated_file = files[0]
        current_file = files[1]

        rotated_content = rotated_file.read_text()
        assert "msg4" in rotated_content
        assert rotated_content.strip().endswith("msg4")

        current_content = current_file.read_text()
        assert "msg5" in current_content

    def test_rotation_level_integer_threshold(self, tmp_path_local):
        i = logger.add(
            tmp_path_local / "test.log", rotation="level", rotation_level=30, format="{message}"
        )
        logger.debug("msg1")
        logger.warning("msg2")
        logger.debug("msg3")
        logger.remove(i)

        files = sorted(tmp_path_local.iterdir())
        assert len(files) == 2

        rotated_file = files[0]
        current_file = files[1]

        rotated_content = rotated_file.read_text()
        assert "msg2" in rotated_content
        assert rotated_content.strip().endswith("msg2")

        current_content = current_file.read_text()
        assert "msg3" in current_content

    def test_rotation_level_string_threshold(self, tmp_path_local):
        i = logger.add(
            tmp_path_local / "test.log",
            rotation="level",
            rotation_level="ERROR",
            format="{message}",
        )
        logger.debug("msg1")
        logger.warning("msg2")
        logger.error("msg3")
        logger.debug("msg4")
        logger.remove(i)

        files = sorted(tmp_path_local.iterdir())
        assert len(files) == 2

        rotated_content = files[0].read_text()
        assert "msg3" in rotated_content
        assert rotated_content.strip().endswith("msg3")

        current_content = files[1].read_text()
        assert "msg4" in current_content

    def test_rotation_level_info_override(self, tmp_path_local):
        i = logger.add(
            tmp_path_local / "test.log",
            rotation="level",
            rotation_level="INFO",
            format="{message}",
        )
        logger.debug("msg1")
        logger.info("msg2")
        logger.debug("msg3")
        logger.remove(i)

        files = sorted(tmp_path_local.iterdir())
        assert len(files) == 2

        rotated_content = files[0].read_text()
        assert "msg2" in rotated_content
        assert rotated_content.strip().endswith("msg2")

        current_content = files[1].read_text()
        assert "msg3" in current_content


class TestLevelRotationPostWrite:
    def test_triggering_record_is_last_in_rotated_file(self, tmp_path_local):
        i = logger.add(tmp_path_local / "test.log", rotation="level", format="{message}")
        logger.debug("before")
        logger.error("trigger")
        logger.debug("after")
        logger.remove(i)

        files = sorted(tmp_path_local.iterdir())
        assert len(files) == 2

        rotated_content = files[0].read_text()
        lines = rotated_content.strip().split("\n")
        assert lines[-1] == "trigger"
        assert "before" in rotated_content

    def test_triggering_record_flushed_before_rotation(self, tmp_path_local):
        i = logger.add(tmp_path_local / "test.log", rotation="level", format="{message}")
        logger.error("critical message")
        logger.debug("next message")
        logger.remove(i)

        files = sorted(tmp_path_local.iterdir())
        assert len(files) == 2

        rotated_content = files[0].read_text()
        assert "critical message" in rotated_content

    def test_multiple_triggers_create_multiple_rotations(self, tmp_path_local):
        i = logger.add(tmp_path_local / "test.log", rotation="level", format="{message}")
        logger.debug("a")
        logger.error("b")
        logger.debug("c")
        logger.error("d")
        logger.debug("e")
        logger.remove(i)

        files = sorted(tmp_path_local.iterdir())
        assert len(files) == 3

        first_rotated = files[0].read_text()
        assert first_rotated.strip().endswith("b")

        second_rotated = files[1].read_text()
        assert second_rotated.strip().endswith("d")

        current = files[2].read_text()
        assert "e" in current


class TestCombiningTriggers:
    def test_list_rotation_size_or_level(self, tmp_path_local):
        i = logger.add(
            tmp_path_local / "test.log",
            rotation=["10 MB", "level"],
            rotation_level="ERROR",
            format="{message}",
        )
        logger.debug("msg1")
        logger.error("msg2")
        logger.debug("msg3")
        logger.remove(i)

        files = sorted(tmp_path_local.iterdir())
        assert len(files) == 2

        rotated_content = files[0].read_text()
        assert "msg2" in rotated_content
        assert rotated_content.strip().endswith("msg2")

    def test_list_rotation_size_triggers(self, tmp_path_local):
        i = logger.add(
            tmp_path_local / "test.log",
            rotation=["8 B", "level"],
            rotation_level="CRITICAL",
            format="{message}",
        )
        logger.debug("abcdefgh")
        logger.debug("next")
        logger.remove(i)

        files = sorted(tmp_path_local.iterdir())
        assert len(files) >= 2

    def test_list_rotation_level_triggers_with_size(self, tmp_path_local):
        i = logger.add(
            tmp_path_local / "test.log",
            rotation=["10 MB", "level"],
            rotation_level="WARNING",
            format="{message}",
        )
        logger.debug("small")
        logger.warning("trigger")
        logger.debug("after")
        logger.remove(i)

        files = sorted(tmp_path_local.iterdir())
        assert len(files) == 2

        rotated_content = files[0].read_text()
        assert rotated_content.strip().endswith("trigger")

    def test_deduplication_single_rotation(self, tmp_path_local):
        i = logger.add(
            tmp_path_local / "test.log",
            rotation=["5 B", "level"],
            rotation_level="ERROR",
            format="{message}",
        )
        logger.error("abcdefghij")
        logger.debug("x")
        logger.remove(i)

        files = sorted(tmp_path_local.iterdir())
        assert len(files) == 2, (
            f"Expected exactly 2 files (1 rotated + 1 current), got {len(files)}: "
            f"{[f.name for f in files]}. "
            f"A spurious rotation may have created a ghost file."
        )

        rotated_content = files[0].read_text()
        assert "abcdefghij" in rotated_content
        assert rotated_content.strip().endswith("abcdefghij")

        current_content = files[1].read_text()
        assert current_content.strip() == "x"

        for f in files:
            assert f.stat().st_size > 0, f"File {f.name} is empty (0-byte ghost file)"

    def test_deduplication_triggering_record_in_rotated_file(self, tmp_path_local):
        i = logger.add(
            tmp_path_local / "test.log",
            rotation=["5 B", "level"],
            rotation_level="ERROR",
            format="{message}",
        )
        logger.error("abcdefghij")
        logger.debug("after")
        logger.remove(i)

        files = sorted(tmp_path_local.iterdir())
        rotated_content = files[0].read_text()
        assert "abcdefghij" in rotated_content

    def test_no_empty_rotated_files(self, tmp_path_local):
        i = logger.add(
            tmp_path_local / "test.log",
            rotation=["5 B", "level"],
            rotation_level="ERROR",
            format="{message}",
        )
        logger.error("abcdefghij")
        logger.debug("y")
        logger.debug("z")
        logger.remove(i)

        files = sorted(tmp_path_local.iterdir())
        assert len(files) == 2, (
            f"Expected exactly 2 files, got {len(files)}: {[f.name for f in files]}. "
            f"The size trigger may have fired on an empty file after level-based rotation."
        )

        for f in files:
            assert f.stat().st_size > 0, f"Rotated file {f.name} is empty (ghost file)"

        rotated_content = files[0].read_text()
        assert "abcdefghij" in rotated_content
        assert rotated_content.strip().endswith("abcdefghij")

        current_content = files[1].read_text()
        assert "y" in current_content
        assert "z" in current_content


class TestThreadSafety:
    def test_rotation_within_lock_context(self, tmp_path_local):
        i = logger.add(tmp_path_local / "test.log", rotation="level", format="{message}")
        errors = []

        def writer(level_func, msg):
            try:
                level_func(msg)
            except Exception as e:
                errors.append(e)

        threads = []
        for j in range(5):
            t = threading.Thread(target=writer, args=(logger.error, f"error_{j}"))
            threads.append(t)
        for j in range(5):
            t = threading.Thread(target=writer, args=(logger.debug, f"debug_{j}"))
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        logger.remove(i)

        assert len(errors) == 0

        all_content = ""
        for f in tmp_path_local.iterdir():
            all_content += f.read_text()

        for j in range(5):
            assert f"error_{j}" in all_content
            assert f"debug_{j}" in all_content

    def test_no_messages_written_to_old_file_after_rotation(self, tmp_path_local):
        i = logger.add(tmp_path_local / "test.log", rotation="level", format="{message}")

        logger.debug("before")
        logger.error("trigger")
        logger.debug("after1")
        logger.debug("after2")
        logger.remove(i)

        files = sorted(tmp_path_local.iterdir())
        rotated_content = files[0].read_text()
        assert "after1" not in rotated_content
        assert "after2" not in rotated_content
        assert rotated_content.strip().endswith("trigger")

    def test_concurrent_writes_no_interleaving(self, tmp_path_local):
        i = logger.add(tmp_path_local / "test.log", rotation="level", format="{message}")

        barrier = threading.Barrier(10)
        results = []

        def write_messages(level_func, msg):
            barrier.wait()
            level_func(msg)

        threads = []
        for j in range(5):
            t = threading.Thread(target=write_messages, args=(logger.error, f"E{j}"))
            threads.append(t)
        for j in range(5):
            t = threading.Thread(target=write_messages, args=(logger.debug, f"D{j}"))
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        logger.remove(i)

        all_lines = []
        for f in sorted(tmp_path_local.iterdir()):
            content = f.read_text()
            all_lines.extend(content.strip().split("\n") if content.strip() else [])

        for j in range(5):
            assert f"E{j}" in all_lines
            assert f"D{j}" in all_lines


class TestEdgeCases:
    def test_no_rotation_when_below_threshold(self, tmp_path_local):
        i = logger.add(tmp_path_local / "test.log", rotation="level", format="{message}")
        logger.debug("msg1")
        logger.info("msg2")
        logger.warning("msg3")
        logger.remove(i)

        files = list(tmp_path_local.iterdir())
        assert len(files) == 1
        content = files[0].read_text()
        assert "msg1" in content
        assert "msg2" in content
        assert "msg3" in content

    def test_rotation_on_exact_threshold(self, tmp_path_local):
        i = logger.add(
            tmp_path_local / "test.log", rotation="level", rotation_level=40, format="{message}"
        )
        logger.error("at_threshold")
        logger.debug("after")
        logger.remove(i)

        files = sorted(tmp_path_local.iterdir())
        assert len(files) == 2
        rotated_content = files[0].read_text()
        assert "at_threshold" in rotated_content

    def test_rotation_level_critical(self, tmp_path_local):
        i = logger.add(
            tmp_path_local / "test.log",
            rotation="level",
            rotation_level="CRITICAL",
            format="{message}",
        )
        logger.error("no_rotate")
        logger.critical("yes_rotate")
        logger.debug("after")
        logger.remove(i)

        files = sorted(tmp_path_local.iterdir())
        assert len(files) == 2
        rotated_content = files[0].read_text()
        assert "yes_rotate" in rotated_content
        assert rotated_content.strip().endswith("yes_rotate")

    def test_empty_file_before_trigger(self, tmp_path_local):
        i = logger.add(tmp_path_local / "test.log", rotation="level", format="{message}")
        logger.error("first_and_trigger")
        logger.debug("second")
        logger.remove(i)

        files = sorted(tmp_path_local.iterdir())
        assert len(files) == 2
        rotated_content = files[0].read_text()
        assert "first_and_trigger" in rotated_content

    def test_rotation_level_with_custom_level_number(self, tmp_path_local):
        i = logger.add(
            tmp_path_local / "test.log", rotation="level", rotation_level=25, format="{message}"
        )
        logger.debug("d")
        logger.warning("w")
        logger.debug("after")
        logger.remove(i)

        files = sorted(tmp_path_local.iterdir())
        assert len(files) == 2
        rotated_content = files[0].read_text()
        assert "w" in rotated_content
