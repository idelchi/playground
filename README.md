# dircmp

A tool to compare two directories by file content.

---

Compare two directories by file content, regardless of file names or paths.

## What it does

`dircmp` compares two directory trees and returns `ok` if they contain the exact same files by content, or `fail` with a detailed report showing what differs.

Files are compared using SHA256 hashes. File names, paths, and directory structure don't matter—only that every file's content in directory A exists in directory B (and vice versa).

**Think of it as comparing multisets of file contents:**

- dir1: `[A, B, C]` vs dir2: `[B, A, C]` → **ok** (same content, different order/names)
- dir1: `[A, A, B]` vs dir2: `[A, B]` → **fail** (different counts)

## Installation

```bash
go build -o dircmp
```

Or install directly:

```bash
go install gitlab.garfield-labs.com/apps/dircmp@latest
```

## Quick start

```bash
# Compare two directories
dircmp /path/to/backup /path/to/restore

# With verbose progress reporting
dircmp -v /large/dir1 /large/dir2
```

## Usage

```bash
dircmp [flags] <dir_a> <dir_b>
```

**Flags:**

- `-v`, `--verbose` - Show verbose output with progress reporting
- `--version` - Show version information
- `-h`, `--help` - Show help message

**Exit codes:**

- `0` - Directories match
- `1` - Directories differ
- `2` - Error occurred

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

### Verbose mode

Enable verbose output to see progress during scanning:

```bash
$ dircmp -v large_dir1/ large_dir2/
Scanning large_dir1/...
Using 16 workers for hashing
Found 1000 files...
Hashed 100 files...
Hashed 200 files...
Found 1500 files (1200 unique) in large_dir1/
Scanning large_dir2/...
Using 16 workers for hashing
Found 1000 files...
Hashed 100 files...
Hashed 200 files...
Found 1500 files (1200 unique) in large_dir2/

================================================================================
DIRECTORY COMPARISON
================================================================================
...
```

## How it works

1. Recursively scan both directories with `fastwalk`
2. Compute SHA256 hash for each file (concurrent workers = CPU cores)
3. Build multisets: `{hash: count}`
4. Compare multisets - match if all hashes have same counts

**Performance optimizations:**

- Fast directory traversal using `github.com/charlievieth/fastwalk`
- Concurrent file hashing using all available CPU cores
- Buffer pooling to reduce memory allocations
- Optimized for large directory trees

## Use cases

**Verify backup integrity**
Content matches, regardless of file organization or naming.

**Compare deployments**
Ensure two servers have identical files deployed.

**Validate migrations**
Confirm data copied correctly with different organization.

**CI/CD verification**
Check build artifacts match expected content.

## Notes

- Only regular files compared (symlinks, devices ignored)
- Empty directories ignored
- Unreadable files generate warnings but don't stop comparison
- Duplicate files (same content, multiple copies) are counted
