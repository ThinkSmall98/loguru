import os
import pathlib
import tempfile
import threading
import time

import pytest

from loguru import logger


@pytest.fixture
def tmp_path_local(reset_logger):
    with tempfile.TemporaryDirectory(dir=".") as tmp_path:
        yield pathlib.Path(tmp_path)
        logger.remove()


def test_rotation_level_thread_safety(tmp_path_local):
    """
    Test that level-based rotation is thread-safe and that no messages
    are written to the wrong file after rotation is triggered.
    
    This verifies Guideline 3: The rotation must be atomic relative to
    the sink's write-lock.
    """
    logger.add(tmp_path_local / "test.log", rotation="level", rotation_level="ERROR", format="{message}")
    
    messages_logged = []
    barrier = threading.Barrier(10)
    
    def log_messages(thread_id):
        barrier.wait()
        
        for i in range(5):
            if thread_id == 0 and i == 2:
                msg = f"Thread {thread_id}: ERROR {i}"
                logger.error(msg)
            else:
                msg = f"Thread {thread_id}: INFO {i}"
                logger.info(msg)
            messages_logged.append(msg)
            time.sleep(0.001)
    
    threads = []
    for i in range(10):
        t = threading.Thread(target=log_messages, args=(i,))
        threads.append(t)
        t.start()
    
    for t in threads:
        t.join()
    
    files = sorted(tmp_path_local.iterdir())
    
    assert len(files) == 2
    
    rotated_file = [f for f in files if f.name.startswith("test.2")][0]
    current_file = [f for f in files if f.name == "test.log"][0]
    
    rotated_content = rotated_file.read_text()
    current_content = current_file.read_text()
    
    all_lines = rotated_content.split('\n') + current_content.split('\n')
    all_lines = [line for line in all_lines if line]
    
    assert len(all_lines) == 50
    
    assert "Thread 0: ERROR 2" in rotated_content


def test_rotation_level_atomic_with_lock(tmp_path_local):
    """
    Verify that the rotation happens within the same lock context as write and flush.
    
    This test checks the code structure requirement from the problem statement:
    "If the rotate() call is outside the with self._lock: block, it's wrong."
    
    Since we can't directly access the lock in tests, we verify behavior:
    - All messages are accounted for
    - No message appears in both files
    - The triggering message is the last in the rotated file
    """
    logger.add(tmp_path_local / "test.log", rotation="level", rotation_level="WARNING", format="{message}")
    
    logger.info("Message 1")
    logger.info("Message 2")
    logger.warning("Trigger rotation")
    logger.info("Message 3")
    
    files = sorted(tmp_path_local.iterdir())
    assert len(files) == 2
    
    rotated_file = [f for f in files if f.name.startswith("test.2")][0]
    current_file = [f for f in files if f.name == "test.log"][0]
    
    rotated_lines = [line for line in rotated_file.read_text().split('\n') if line]
    current_lines = [line for line in current_file.read_text().split('\n') if line]
    
    assert rotated_lines == ["Message 1", "Message 2", "Trigger rotation"]
    assert current_lines == ["Message 3"]
    
    assert rotated_lines[-1] == "Trigger rotation"
