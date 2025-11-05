// Package dircmp provides directory comparison functionality.
package dircmp

// File represents a file with its hash and path.
type File struct {
	Hash string
	Path string
	Size int64
}

// Scan holds scan results for a directory.
type Scan struct {
	Files       []File
	HashCounts  map[string]int      // hash -> count
	HashToFiles map[string][]string // hash -> file paths
	TotalFiles  int
	TotalSize   int64
}

// Diff represents differences between directories.
type Diff struct {
	MissingInB map[string]int      // hash -> count (files in A not in B)
	MissingInA map[string]int      // hash -> count (files in B not in A)
	HashToA    map[string][]string // hash -> paths in A
	HashToB    map[string][]string // hash -> paths in B
}
