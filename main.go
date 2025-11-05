package main

import (
	"crypto/sha256"
	"flag"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"runtime"
	"sort"
	"strings"
	"sync"
	"sync/atomic"

	"github.com/charlievieth/fastwalk"
)

var (
	verbose bool
	version = "dev"
)

// File represents a file with its hash and path
type File struct {
	Hash string
	Path string
	Size int64
}

// DirScan holds scan results for a directory
type DirScan struct {
	Files       []File
	HashCounts  map[string]int      // hash -> count
	HashToFiles map[string][]string // hash -> file paths
	TotalFiles  int
	TotalSize   int64
}

// Diff represents differences between directories
type Diff struct {
	MissingInB map[string]int      // hash -> count (files in A not in B)
	MissingInA map[string]int      // hash -> count (files in B not in A)
	HashToA    map[string][]string // hash -> paths in A
	HashToB    map[string][]string // hash -> paths in B
}

func init() {
	flag.BoolVar(&verbose, "verbose", false, "enable verbose output")
	flag.BoolVar(&verbose, "v", false, "enable verbose output (shorthand)")
	flag.Usage = usage
}

func usage() {
	fmt.Fprintf(os.Stderr, "dircmp %s\n\n", version)
	fmt.Fprintln(os.Stderr, "Usage: dircmp [options] <dir_a> <dir_b>")
	fmt.Fprintln(os.Stderr, "")
	fmt.Fprintln(os.Stderr, "Compares two directories by file content.")
	fmt.Fprintln(os.Stderr, "Returns 'ok' if both contain identical files (regardless of names/paths).")
	fmt.Fprintln(os.Stderr, "Returns 'fail' with detailed report if differences exist.")
	fmt.Fprintln(os.Stderr, "")
	fmt.Fprintln(os.Stderr, "Options:")
	flag.PrintDefaults()
	fmt.Fprintln(os.Stderr, "")
	fmt.Fprintln(os.Stderr, "Exit codes:")
	fmt.Fprintln(os.Stderr, "  0  Directories match")
	fmt.Fprintln(os.Stderr, "  1  Directories differ")
	fmt.Fprintln(os.Stderr, "  2  Error occurred")
}

func main() {
	flag.Parse()

	if flag.NArg() != 2 {
		usage()
		os.Exit(1)
	}

	dirA := flag.Arg(0)
	dirB := flag.Arg(1)

	// Scan both directories
	logf("Scanning %s...", dirA)
	scanA, err := scan(dirA)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error scanning %s: %v\n", dirA, err)
		os.Exit(2)
	}
	logf("Found %d files (%d unique) in %s", scanA.TotalFiles, len(scanA.HashCounts), dirA)

	logf("Scanning %s...", dirB)
	scanB, err := scan(dirB)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error scanning %s: %v\n", dirB, err)
		os.Exit(2)
	}
	logf("Found %d files (%d unique) in %s", scanB.TotalFiles, len(scanB.HashCounts), dirB)

	// Compare and report
	if compare(dirA, dirB, scanA, scanB) {
		os.Exit(0)
	}
	os.Exit(1)
}

// logf prints a message if verbose mode is enabled
func logf(format string, args ...interface{}) {
	if verbose {
		fmt.Fprintf(os.Stderr, format+"\n", args...)
	}
}

// fileJob represents a file to hash
type fileJob struct {
	path    string
	relPath string
	size    int64
}

// fileResult represents a hashed file
type fileResult struct {
	hash    string
	relPath string
	size    int64
}

// scan recursively scans a directory and computes file hashes concurrently
func scan(dir string) (*DirScan, error) {
	absDir, err := filepath.Abs(dir)
	if err != nil {
		return nil, err
	}

	info, err := os.Stat(absDir)
	if err != nil {
		return nil, err
	}
	if !info.IsDir() {
		return nil, fmt.Errorf("not a directory: %s", absDir)
	}

	// Setup worker pool
	numWorkers := runtime.NumCPU()
	logf("Using %d workers for hashing", numWorkers)
	jobs := make(chan fileJob, numWorkers*2)
	results := make(chan fileResult, numWorkers*2)
	var wg sync.WaitGroup

	// Progress tracking
	var filesFound, filesHashed atomic.Int64

	// Start workers
	for i := 0; i < numWorkers; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for job := range jobs {
				hash, err := hashFile(job.path)
				if err != nil {
					fmt.Fprintf(os.Stderr, "warning: failed to hash %s: %v\n", job.relPath, err)
					continue
				}

				hashed := filesHashed.Add(1)
				if verbose && hashed%100 == 0 {
					logf("Hashed %d files...", hashed)
				}

				results <- fileResult{
					hash:    hash,
					relPath: job.relPath,
					size:    job.size,
				}
			}
		}()
	}

	// Collect results in background
	scan := &DirScan{
		Files:       []File{},
		HashCounts:  make(map[string]int),
		HashToFiles: make(map[string][]string),
	}
	var mu sync.Mutex
	var collectWg sync.WaitGroup
	collectWg.Add(1)
	go func() {
		defer collectWg.Done()
		for result := range results {
			file := File{
				Hash: result.hash,
				Path: result.relPath,
				Size: result.size,
			}
			mu.Lock()
			scan.Files = append(scan.Files, file)
			scan.HashCounts[result.hash]++
			scan.HashToFiles[result.hash] = append(scan.HashToFiles[result.hash], result.relPath)
			scan.TotalFiles++
			scan.TotalSize += result.size
			mu.Unlock()
		}
	}()

	// Walk directory using fastwalk
	conf := fastwalk.Config{
		Follow: false,
	}
	err = fastwalk.Walk(&conf, absDir, func(path string, d os.DirEntry, err error) error {
		if err != nil {
			fmt.Fprintf(os.Stderr, "warning: %v\n", err)
			return nil
		}

		if !d.Type().IsRegular() {
			return nil
		}

		info, err := d.Info()
		if err != nil {
			fmt.Fprintf(os.Stderr, "warning: %v\n", err)
			return nil
		}

		relPath, _ := filepath.Rel(absDir, path)

		found := filesFound.Add(1)
		if verbose && found%1000 == 0 {
			logf("Found %d files...", found)
		}

		jobs <- fileJob{
			path:    path,
			relPath: relPath,
			size:    info.Size(),
		}

		return nil
	})

	close(jobs)
	wg.Wait()
	close(results)
	collectWg.Wait()

	if err != nil {
		return nil, err
	}

	return scan, nil
}

// Buffer pool to reduce allocations
var bufPool = sync.Pool{
	New: func() interface{} {
		b := make([]byte, 32*1024) // 32KB buffer
		return &b
	},
}

// hashFile computes SHA256 hash of a file
func hashFile(path string) (string, error) {
	f, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer f.Close()

	h := sha256.New()
	bufPtr := bufPool.Get().(*[]byte)
	defer bufPool.Put(bufPtr)

	if _, err := io.CopyBuffer(h, f, *bufPtr); err != nil {
		return "", err
	}

	return fmt.Sprintf("%x", h.Sum(nil)), nil
}

// compare compares two directory scans and prints results
func compare(dirA, dirB string, scanA, scanB *DirScan) bool {
	fmt.Println()
	fmt.Println(strings.Repeat("=", 80))
	fmt.Println("DIRECTORY COMPARISON")
	fmt.Println(strings.Repeat("=", 80))
	fmt.Printf("\nA: %s\n", dirA)
	fmt.Printf("B: %s\n", dirB)
	fmt.Println()

	// Print summaries
	fmt.Printf("Files in A: %d (%.2f MB)\n", scanA.TotalFiles, float64(scanA.TotalSize)/(1024*1024))
	fmt.Printf("Files in B: %d (%.2f MB)\n", scanB.TotalFiles, float64(scanB.TotalSize)/(1024*1024))
	fmt.Printf("Unique content in A: %d\n", len(scanA.HashCounts))
	fmt.Printf("Unique content in B: %d\n", len(scanB.HashCounts))
	fmt.Println()

	// Compare hash multisets
	diff := computeDiff(scanA, scanB)

	if len(diff.MissingInB) == 0 && len(diff.MissingInA) == 0 {
		fmt.Println("✓ RESULT: ok")
		fmt.Println()
		fmt.Println("Directories contain identical files (by content).")

		// Show if there are duplicates or different naming
		showDuplicates(scanA, scanB)

		fmt.Println(strings.Repeat("=", 80))
		return true
	}

	fmt.Println("✗ RESULT: fail")
	fmt.Println()
	fmt.Println("Directories contain different files.")
	fmt.Println()

	// Report differences
	reportDiff(diff, scanA, scanB)

	fmt.Println(strings.Repeat("=", 80))
	return false
}

// computeDiff computes the difference between two scans
func computeDiff(scanA, scanB *DirScan) Diff {
	diff := Diff{
		MissingInB: make(map[string]int),
		MissingInA: make(map[string]int),
		HashToA:    scanA.HashToFiles,
		HashToB:    scanB.HashToFiles,
	}

	// Find what's in A but not enough copies in B
	for hash, countA := range scanA.HashCounts {
		countB := scanB.HashCounts[hash]
		if countA > countB {
			diff.MissingInB[hash] = countA - countB
		}
	}

	// Find what's in B but not enough copies in A
	for hash, countB := range scanB.HashCounts {
		countA := scanA.HashCounts[hash]
		if countB > countA {
			diff.MissingInA[hash] = countB - countA
		}
	}

	return diff
}

// reportDiff prints a detailed difference report
func reportDiff(diff Diff, scanA, scanB *DirScan) {
	if len(diff.MissingInB) > 0 {
		totalMissing := 0
		for _, count := range diff.MissingInB {
			totalMissing += count
		}
		fmt.Printf("Missing in B: %d files (%d unique)\n\n", totalMissing, len(diff.MissingInB))

		hashes := sortedKeys(diff.MissingInB)
		limit := 10
		if len(hashes) < limit {
			limit = len(hashes)
		}

		for i := 0; i < limit; i++ {
			hash := hashes[i]
			count := diff.MissingInB[hash]
			files := diff.HashToA[hash]

			if count == 1 {
				fmt.Printf("  [%s...] (%s)\n", hash[:16], files[0])
			} else {
				fmt.Printf("  [%s...] (need %d more copies)\n", hash[:16], count)
				for _, f := range files {
					fmt.Printf("    - %s\n", f)
				}
			}
		}

		if len(hashes) > limit {
			fmt.Printf("  ... and %d more\n", len(hashes)-limit)
		}
		fmt.Println()
	}

	if len(diff.MissingInA) > 0 {
		totalExtra := 0
		for _, count := range diff.MissingInA {
			totalExtra += count
		}
		fmt.Printf("Extra in B: %d files (%d unique)\n\n", totalExtra, len(diff.MissingInA))

		hashes := sortedKeys(diff.MissingInA)
		limit := 10
		if len(hashes) < limit {
			limit = len(hashes)
		}

		for i := 0; i < limit; i++ {
			hash := hashes[i]
			count := diff.MissingInA[hash]
			files := diff.HashToB[hash]

			if count == 1 {
				fmt.Printf("  [%s...] (%s)\n", hash[:16], files[0])
			} else {
				fmt.Printf("  [%s...] (%d extra copies)\n", hash[:16], count)
				for _, f := range files {
					fmt.Printf("    - %s\n", f)
				}
			}
		}

		if len(hashes) > limit {
			fmt.Printf("  ... and %d more\n", len(hashes)-limit)
		}
		fmt.Println()
	}
}

// showDuplicates shows information about duplicates and different paths
func showDuplicates(scanA, scanB *DirScan) {
	var duplicatesA, duplicatesB []string
	var differentPaths []string

	for hash, filesA := range scanA.HashToFiles {
		if len(filesA) > 1 {
			duplicatesA = append(duplicatesA, hash)
		}

		filesB, exists := scanB.HashToFiles[hash]
		if exists && !pathsEqual(filesA, filesB) {
			differentPaths = append(differentPaths, hash)
		}
	}

	for hash, filesB := range scanB.HashToFiles {
		if len(filesB) > 1 {
			if _, exists := scanA.HashToFiles[hash]; !exists {
				duplicatesB = append(duplicatesB, hash)
			}
		}
	}

	if len(duplicatesA) > 0 || len(duplicatesB) > 0 {
		fmt.Println()
		fmt.Println("Note: Duplicates detected (same content, multiple copies)")

		if len(duplicatesA) > 0 {
			fmt.Printf("  In A: %d sets\n", len(duplicatesA))
		}
		if len(duplicatesB) > 0 {
			fmt.Printf("  In B: %d sets\n", len(duplicatesB))
		}
	}

	if len(differentPaths) > 0 {
		fmt.Println()
		fmt.Printf("Note: %d files with different names/paths between A and B\n", len(differentPaths))
	}
}

// pathsEqual checks if two path lists are equal (order-independent)
func pathsEqual(a, b []string) bool {
	if len(a) != len(b) {
		return false
	}
	sortedA := make([]string, len(a))
	sortedB := make([]string, len(b))
	copy(sortedA, a)
	copy(sortedB, b)
	sort.Strings(sortedA)
	sort.Strings(sortedB)
	for i := range sortedA {
		if sortedA[i] != sortedB[i] {
			return false
		}
	}
	return true
}

// sortedKeys returns sorted keys from a map
func sortedKeys(m map[string]int) []string {
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	return keys
}
