package dircmp

// File represents a file with its content hash, path, and size.
type File struct {
	// Hash is the SHA256 hash of the file content.
	Hash string
	// Path is the relative path of the file.
	Path string
	// Size is the file size in bytes.
	Size int64
}

// Scan represents the scan results for a directory.
type Scan struct {
	// Files holds all scanned files.
	Files []File
	// HashCounts maps file hashes to their occurrence count.
	HashCounts map[string]int
	// HashToFiles maps file hashes to their relative paths.
	HashToFiles map[string][]string
	// TotalFiles is the total number of files scanned.
	TotalFiles int
	// TotalSize is the total size of all files in bytes.
	TotalSize int64
}

// Diff represents the differences between two directory scans.
type Diff struct {
	// MissingInB maps hashes to the count of files in A but not in B (or not enough copies in B).
	MissingInB map[string]int
	// MissingInA maps hashes to the count of files in B but not in A (or not enough copies in A).
	MissingInA map[string]int
	// HashToA maps file hashes to their paths in directory A.
	HashToA map[string][]string
	// HashToB maps file hashes to their paths in directory B.
	HashToB map[string][]string
}
