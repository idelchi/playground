# dircmp

Compare two directories by content, regardless of file names or paths.

## Overview

`dircmp` compares two directory trees and returns `ok` if they contain the exact same files by content, or `fail` with a detailed report if they differ.

Files are compared using SHA256 hashes. File names, paths, and directory structure don't matter—only that every file's content in directory A exists in directory B and vice versa.

## Key Concept

Think of it as comparing multisets of file contents:
- `hash(all files in dir1/**)` == `hash(all files in dir2/**)`

If dir1 has files with content [A, B, C] and dir2 has files with content [B, A, C], they match—even if names/paths differ.

If dir1 has [A, A, B] and dir2 has [A, B], they don't match (different counts).

## Installation

```bash
go build -o dircmp
```

## Usage

```bash
dircmp <dir_a> <dir_b>
```

### Exit Codes

- `0`: Directories match
- `1`: Directories differ
- `2`: Error (directory not found, permission denied, etc.)

## Examples

### Same content, different names/paths

```
$ tree backup/
backup/
├── data.txt
└── notes.txt

$ tree restore/
restore/
├── subdir
│   └── file1.txt
└── file2.txt

$ dircmp backup/ restore/

================================================================================
DIRECTORY COMPARISON
================================================================================

A: backup/
B: restore/

Files in A: 2 (0.00 MB)
Files in B: 2 (0.00 MB)
Unique content in A: 2
Unique content in B: 2

✓ RESULT: ok

Directories contain identical files (by content).

Note: 2 files with different names/paths between A and B
================================================================================
```

### Different content

```
$ dircmp dir1/ dir2/

================================================================================
DIRECTORY COMPARISON
================================================================================

A: dir1/
B: dir2/

Files in A: 3 (0.02 MB)
Files in B: 2 (0.01 MB)
Unique content in A: 3
Unique content in B: 2

✗ RESULT: fail

Directories contain different files.

Missing in B: 2 files (2 unique)

  [a8f5f167f44f4964...] (doc.txt)
  [e3b0c44298fc1c14...] (empty.txt)

Extra in B: 1 files (1 unique)

  [5d41402abc4b2a76...] (new.txt)

================================================================================
```

## Use Cases

- Verify backup integrity (content matches, regardless of file organization)
- Compare deployment directories across servers
- Validate data migrations
- Check if two archives contain the same files
- CI/CD verification

## How It Works

1. Fast directory traversal using `fastwalk`
2. Concurrent file hashing with worker pool (uses all CPU cores)
3. Build multisets of hashes: `{hash: count}`
4. Compare multisets:
   - Match: all hashes have same counts in both dirs
   - Fail: report what's missing/extra

## Performance

- Uses `github.com/charlievieth/fastwalk` for fast directory walking
- Concurrent file hashing (worker pool = number of CPU cores)
- Buffer pooling to reduce memory allocations
- Optimized for large directory trees

## Notes

- Only regular files are compared (symlinks, devices, etc. are ignored)
- Empty directories are ignored
- Warnings printed for unreadable files (comparison continues)
- File counts must match exactly (duplicates matter)