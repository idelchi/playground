# Directory Comparison Tool (dircmp)

A Go application that compares two directories and determines if they contain the exact same files based on content (regardless of file names or paths).

## Features

- **Content-based comparison**: Compares files by their SHA256 hash, not by name or path
- **Recursive scanning**: Traverses all subdirectories
- **Comprehensive reporting**: Detailed breakdown of differences when directories don't match
- **Duplicate detection**: Identifies files with identical content but different names
- **Clear output**: Returns "OK" or "FAIL" with human-readable reports
- **Fast and efficient**: Written in Go for performance

## Requirements

- Go 1.16 or higher (for building)
- No external dependencies

## Installation

### Build from Source

```bash
go build -o dircmp
```

This will create a `dircmp` executable in the current directory.

### Install Globally

```bash
go install
```

This will install `dircmp` to your `$GOPATH/bin` directory.

## Usage

```bash
./dircmp <directory_a> <directory_b>
```

### Arguments

- `directory_a`: Path to the first directory to compare
- `directory_b`: Path to the second directory to compare

### Exit Codes

- `0`: Directories match (OK)
- `1`: Directories differ (FAIL)
- `2`: Error occurred (e.g., directory not found)

## Examples

### Example 1: Matching Directories

```bash
$ ./dircmp /path/to/dir1 /path/to/dir2
Scanning directory A: /path/to/dir1
Scanning directory B: /path/to/dir2

================================================================================
DIRECTORY COMPARISON REPORT
================================================================================

Directory A: /path/to/dir1
Directory B: /path/to/dir2

Total files in A: 5
Total files in B: 5
Unique files in A (by content): 5
Unique files in B (by content): 5

✓ RESULT: OK
The directories contain the exact same files (by content).
================================================================================
```

### Example 2: Directories with Differences

```bash
$ ./dircmp /path/to/dir1 /path/to/dir2
Scanning directory A: /path/to/dir1
Scanning directory B: /path/to/dir2

================================================================================
DIRECTORY COMPARISON REPORT
================================================================================

Directory A: /path/to/dir1
Directory B: /path/to/dir2

Total files in A: 10
Total files in B: 8
Unique files in A (by content): 8
Unique files in B (by content): 6

✗ RESULT: FAIL
The directories contain different files.

File count mismatch: A has 2 more files than B

Files present ONLY in A (3 unique files):
  Hash 3a52ce780950d4d9...
    - docs/extra.txt
    - images/logo.png
  Hash 7b3d4e5f6a7c8b9a...
    - scripts/deploy.sh
  ...

Files present ONLY in B (1 unique files):
  Hash 9f8e7d6c5b4a3210...
    - config/settings.json

Files present in BOTH directories (5 unique files):
  (Showing first 5)
  Hash 1a2b3c4d5e6f7g8h...
    A: src/main.go
    B: application/main.go
  ...
================================================================================
```

### Example 3: Check Exit Code

```bash
$ ./dircmp dir1 dir2
$ echo $?
0  # Directories match

$ ./dircmp dir1 dir3
$ echo $?
1  # Directories differ
```

## How It Works

1. **Scanning**: The tool recursively scans both directories and calculates SHA256 hashes for all regular files
2. **Hash Mapping**: Creates a mapping of file hashes to file paths for each directory
3. **Comparison**: Compares the sets of hashes to find:
   - Files only in directory A
   - Files only in directory B
   - Files present in both directories
4. **Result**: Returns "OK" if both directories have exactly the same files (by content), "FAIL" otherwise
5. **Reporting**: Provides detailed information about discrepancies

## Key Points

- **Content-based**: Two files are considered identical if they have the same content, even if they have different names or are in different subdirectories
- **Duplicate handling**: If a directory contains multiple copies of the same file (same content, different names), the tool detects and reports this
- **File count**: The tool checks both the total file count AND unique file content to ensure directories match
- **Efficient**: Uses Go's concurrent file processing capabilities for fast scanning

## Use Cases

- Verifying backup integrity
- Comparing file system snapshots
- Detecting duplicate files across directories
- Validating file migrations or synchronizations
- Testing file system operations
- CI/CD pipeline verification

## Implementation Details

- Uses SHA256 for content hashing
- Processes files in chunks for memory efficiency
- Handles large files gracefully
- Continues processing even if individual files fail (with warnings)
- Uses relative paths for cleaner output

## Limitations

- Only compares regular files (not symlinks, devices, etc.)
- Assumes sufficient permissions to read all files in both directories
- Symlinks are not followed by default

## License

This tool is provided as-is for educational and practical purposes