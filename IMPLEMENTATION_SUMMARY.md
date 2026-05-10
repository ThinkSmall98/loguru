# Level-Based Rotation Implementation Summary

## Overview
Successfully implemented reactive level-based rotation for loguru that triggers rotation after writing messages that meet a specified severity level threshold.

## Key Changes

### 1. Core Implementation Files

#### `loguru/_file_sink.py`
- Added `Rotation.rotation_level()` static method for level-based rotation logic
- Created `Rotation.PostWriteRotation` wrapper class to distinguish post-write rotations
- Modified `FileSink.__init__()` to accept `rotation_level` parameter
- Updated `FileSink.write()` to support both pre-write and post-write rotation triggers
- Implemented deduplication logic: when both triggers activate, only one rotation occurs
- Added `FileSink._parse_rotation_level()` to parse level strings (e.g., "ERROR") or integers (e.g., 40)
- Modified `FileSink._make_rotation_function()` to handle `rotation="level"` string

#### `loguru/_logger.py`
- Updated `Logger.add()` docstring to document `rotation_level` parameter
- Clarified that `rotation="level"` enables level-based rotation

### 2. Implementation Details

#### Post-Write Rotation Mechanism
The rotation occurs **after** the triggering record has been fully written and flushed to disk:
```python
# Check rotation conditions
pre_write_rotation = False
post_write_rotation = False

# Pre-write rotation (size, time) happens before writing
if pre_write_rotation and not post_write_rotation:
    self._terminate_file(is_rotating=True)

# Write and flush the message
self._file.write(message)
self._file.flush()

# Post-write rotation (level) happens after writing
if post_write_rotation:
    self._terminate_file(is_rotating=True)
```

#### Deduplication Logic
When both size-based and level-based triggers activate on the same message:
- Post-write rotation takes precedence
- Only one rotation occurs
- The triggering message is included in the rotated file

#### Thread Safety
- Rotation occurs within the same lock context as write() and flush()
- The Handler's `_protected_lock()` ensures atomicity
- No subsequent writes can occur until the current write() completes

### 3. API Usage

#### Basic Level Rotation
```python
logger.add("file.log", rotation="level", rotation_level="ERROR")
```
- Rotates when ERROR (or higher) messages are logged
- Default level is 40 (ERROR) if `rotation_level` is omitted

#### Combined Triggers
```python
logger.add("file.log", rotation=["10 MB", "level"], rotation_level="ERROR")
```
- Rotates if **either** file size exceeds 10 MB **or** an ERROR is logged
- Follows OR logic for multiple triggers

#### Integer Level Values
```python
logger.add("file.log", rotation="level", rotation_level=20)  # INFO level
```
- Supports direct integer level values
- Standard levels: TRACE=5, DEBUG=10, INFO=20, SUCCESS=25, WARNING=30, ERROR=40, CRITICAL=50

### 4. Test Coverage

#### Unit Tests (`tests/test_rotation_level.py`)
- ✅ Basic level-based rotation
- ✅ Default level (ERROR)
- ✅ Custom integer levels
- ✅ Triggering record is last in rotated file
- ✅ Combined size and level triggers
- ✅ Deduplication when both triggers activate
- ✅ Multiple sequential rotations
- ✅ Different severity levels (CRITICAL, INFO, etc.)
- ✅ Case-insensitive level names
- ✅ Invalid level string/type handling

#### Thread Safety Tests (`tests/test_rotation_level_thread_safety.py`)
- ✅ Concurrent logging from multiple threads
- ✅ Atomic rotation within lock context
- ✅ No messages written to wrong file after rotation

#### Acceptance Criteria
All 5 criteria from the problem statement verified:
1. ✅ `logger.add(..., rotation="level")` works without crashing
2. ✅ `rotation_level="INFO"` correctly overrides default "ERROR"
3. ✅ List of triggers `["10 MB", "level"]` rotates if either is true
4. ✅ Triggering record is always last line in rotated file
5. ✅ Rotation logic is atomic within sink's thread-lock

### 5. Backward Compatibility

- All existing rotation tests pass (132 passed, 9 skipped)
- No breaking changes to existing rotation behavior
- New parameters are optional with sensible defaults

## Files Modified
- `loguru/_file_sink.py` (core implementation)
- `loguru/_logger.py` (documentation)

## Files Added
- `tests/test_rotation_level.py` (11 tests)
- `tests/test_rotation_level_thread_safety.py` (2 tests)
- `demo_rotation_level.py` (demonstration script)
- `test_acceptance_criteria.py` (acceptance verification)

## Verification
Run the test suite:
```bash
# Run all new tests
pytest tests/test_rotation_level.py -v
pytest tests/test_rotation_level_thread_safety.py -v

# Verify backward compatibility
pytest tests/test_filesink_rotation.py -v

# Run acceptance criteria
python test_acceptance_criteria.py
```

All tests pass successfully! ✓
