package main

import (
	"crypto/sha256"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

// FileInfo represents a file with its hash and path
type FileInfo struct {
	Hash         string
	RelativePath string
}

// DirScan holds the results of scanning a directory
type DirScan struct {
	// Map of hash -> list of relative paths with that hash
	HashToFiles map[string][]string
	FileCount   int
}

// ComparisonReport holds the comparison results
type ComparisonReport struct {
	CountA       int
	CountB       int
	UniqueFilesA int
	UniqueFilesB int
	OnlyInA      []string // hashes
	OnlyInB      []string // hashes
	InBoth       []string // hashes
	ScanA        *DirScan
	ScanB        *DirScan
}

// calculateFileHash computes SHA256 hash of a file
func calculateFileHash(filePath string) (string, error) {
	file, err := os.Open(filePath)
	if err != nil {
		return "", err
	}
	defer file.Close()

	hash := sha256.New()
	if _, err := io.Copy(hash, file); err != nil {
		return "", err
	}

	return fmt.Sprintf("%x", hash.Sum(nil)), nil
}

// scanDirectory recursively scans a directory and creates hash mappings
func scanDirectory(dirPath string) (*DirScan, error) {
	scan := &DirScan{
		HashToFiles: make(map[string][]string),
		FileCount:   0,
	}

	// Check if directory exists
	info, err := os.Stat(dirPath)
	if err != nil {
		return nil, fmt.Errorf("error accessing directory: %w", err)
	}
	if !info.IsDir() {
		return nil, fmt.Errorf("path is not a directory: %s", dirPath)
	}

	absDir, err := filepath.Abs(dirPath)
	if err != nil {
		return nil, err
	}

	err = filepath.Walk(absDir, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			fmt.Fprintf(os.Stderr, "Warning: error accessing %s: %v\n", path, err)
			return nil // Continue walking
		}

		// Only process regular files
		if info.Mode().IsRegular() {
			hash, err := calculateFileHash(path)
			if err != nil {
				fmt.Fprintf(os.Stderr, "Warning: error hashing %s: %v\n", path, err)
				return nil // Continue walking
			}

			// Get relative path
			relPath, err := filepath.Rel(absDir, path)
			if err != nil {
				relPath = path
			}

			scan.HashToFiles[hash] = append(scan.HashToFiles[hash], relPath)
			scan.FileCount++
		}

		return nil
	})

	if err != nil {
		return nil, err
	}

	return scan, nil
}

// compareDirectories compares two directory scans
func compareDirectories(dirA, dirB string) (bool, *ComparisonReport, error) {
	fmt.Printf("Scanning directory A: %s\n", dirA)
	scanA, err := scanDirectory(dirA)
	if err != nil {
		return false, nil, err
	}

	fmt.Printf("Scanning directory B: %s\n", dirB)
	scanB, err := scanDirectory(dirB)
	if err != nil {
		return false, nil, err
	}

	// Get hash sets
	hashesA := make(map[string]bool)
	for hash := range scanA.HashToFiles {
		hashesA[hash] = true
	}

	hashesB := make(map[string]bool)
	for hash := range scanB.HashToFiles {
		hashesB[hash] = true
	}

	// Find differences
	var onlyInA, onlyInB, inBoth []string

	for hash := range hashesA {
		if hashesB[hash] {
			inBoth = append(inBoth, hash)
		} else {
			onlyInA = append(onlyInA, hash)
		}
	}

	for hash := range hashesB {
		if !hashesA[hash] {
			onlyInB = append(onlyInB, hash)
		}
	}

	// Sort for consistent output
	sort.Strings(onlyInA)
	sort.Strings(onlyInB)
	sort.Strings(inBoth)

	report := &ComparisonReport{
		CountA:       scanA.FileCount,
		CountB:       scanB.FileCount,
		UniqueFilesA: len(hashesA),
		UniqueFilesB: len(hashesB),
		OnlyInA:      onlyInA,
		OnlyInB:      onlyInB,
		InBoth:       inBoth,
		ScanA:        scanA,
		ScanB:        scanB,
	}

	// Directories match if they have the same unique files and same count
	success := len(onlyInA) == 0 && len(onlyInB) == 0 && scanA.FileCount == scanB.FileCount

	return success, report, nil
}

// printReport prints a comprehensive comparison report
func printReport(success bool, report *ComparisonReport, dirA, dirB string) {
	fmt.Println()
	fmt.Println(strings.Repeat("=", 80))
	fmt.Println("DIRECTORY COMPARISON REPORT")
	fmt.Println(strings.Repeat("=", 80))
	fmt.Printf("\nDirectory A: %s\n", dirA)
	fmt.Printf("Directory B: %s\n", dirB)
	fmt.Println()
	fmt.Printf("Total files in A: %d\n", report.CountA)
	fmt.Printf("Total files in B: %d\n", report.CountB)
	fmt.Printf("Unique files in A (by content): %d\n", report.UniqueFilesA)
	fmt.Printf("Unique files in B (by content): %d\n", report.UniqueFilesB)
	fmt.Println()

	if success {
		fmt.Println("✓ RESULT: OK")
		fmt.Println("The directories contain the exact same files (by content).")

		// Show duplicates if any
		printDuplicates(report)
	} else {
		fmt.Println("✗ RESULT: FAIL")
		fmt.Println("The directories contain different files.")
		fmt.Println()

		// File count mismatch
		if report.CountA != report.CountB {
			diff := report.CountA - report.CountB
			comparison := "more"
			if diff < 0 {
				diff = -diff
				comparison = "fewer"
			}
			fmt.Printf("File count mismatch: A has %d %s files than B\n", diff, comparison)
			fmt.Println()
		}

		// Files only in A
		if len(report.OnlyInA) > 0 {
			fmt.Printf("Files present ONLY in A (%d unique files):\n", len(report.OnlyInA))
			limit := 10
			if len(report.OnlyInA) < limit {
				limit = len(report.OnlyInA)
			}
			for i := 0; i < limit; i++ {
				hash := report.OnlyInA[i]
				files := report.ScanA.HashToFiles[hash]
				fmt.Printf("  Hash %s...:\n", hash[:16])
				for _, f := range files {
					fmt.Printf("    - %s\n", f)
				}
			}
			if len(report.OnlyInA) > limit {
				fmt.Printf("  ... and %d more unique files\n", len(report.OnlyInA)-limit)
			}
			fmt.Println()
		}

		// Files only in B
		if len(report.OnlyInB) > 0 {
			fmt.Printf("Files present ONLY in B (%d unique files):\n", len(report.OnlyInB))
			limit := 10
			if len(report.OnlyInB) < limit {
				limit = len(report.OnlyInB)
			}
			for i := 0; i < limit; i++ {
				hash := report.OnlyInB[i]
				files := report.ScanB.HashToFiles[hash]
				fmt.Printf("  Hash %s...:\n", hash[:16])
				for _, f := range files {
					fmt.Printf("    - %s\n", f)
				}
			}
			if len(report.OnlyInB) > limit {
				fmt.Printf("  ... and %d more unique files\n", len(report.OnlyInB)-limit)
			}
			fmt.Println()
		}

		// Files in both
		if len(report.InBoth) > 0 {
			fmt.Printf("Files present in BOTH directories (%d unique files):\n", len(report.InBoth))
			fmt.Println("  (Showing first 5)")
			limit := 5
			if len(report.InBoth) < limit {
				limit = len(report.InBoth)
			}
			for i := 0; i < limit; i++ {
				hash := report.InBoth[i]
				filesA := report.ScanA.HashToFiles[hash]
				filesB := report.ScanB.HashToFiles[hash]
				fmt.Printf("  Hash %s...:\n", hash[:16])
				fmt.Printf("    A: %s\n", strings.Join(filesA, ", "))
				fmt.Printf("    B: %s\n", strings.Join(filesB, ", "))
			}
			if len(report.InBoth) > limit {
				fmt.Printf("  ... and %d more matching files\n", len(report.InBoth)-limit)
			}
			fmt.Println()
		}
	}

	fmt.Println(strings.Repeat("=", 80))
}

// printDuplicates prints information about duplicate files
func printDuplicates(report *ComparisonReport) {
	// Find duplicates (files with same hash but different paths)
	duplicatesA := make(map[string][]string)
	for hash, files := range report.ScanA.HashToFiles {
		if len(files) > 1 {
			duplicatesA[hash] = files
		}
	}

	duplicatesB := make(map[string][]string)
	for hash, files := range report.ScanB.HashToFiles {
		if len(files) > 1 {
			duplicatesB[hash] = files
		}
	}

	if len(duplicatesA) > 0 || len(duplicatesB) > 0 {
		fmt.Println("\nNote: Duplicate files detected (same content, different names/paths):")

		if len(duplicatesA) > 0 {
			fmt.Printf("\n  In Directory A (%d sets of duplicates):\n", len(duplicatesA))
			count := 0
			for hash, files := range duplicatesA {
				if count >= 5 {
					break
				}
				fmt.Printf("    Hash %s...:\n", hash[:16])
				for _, f := range files {
					fmt.Printf("      - %s\n", f)
				}
				count++
			}
			if len(duplicatesA) > 5 {
				fmt.Printf("    ... and %d more duplicate sets\n", len(duplicatesA)-5)
			}
		}

		if len(duplicatesB) > 0 {
			fmt.Printf("\n  In Directory B (%d sets of duplicates):\n", len(duplicatesB))
			count := 0
			for hash, files := range duplicatesB {
				if count >= 5 {
					break
				}
				fmt.Printf("    Hash %s...:\n", hash[:16])
				for _, f := range files {
					fmt.Printf("      - %s\n", f)
				}
				count++
			}
			if len(duplicatesB) > 5 {
				fmt.Printf("    ... and %d more duplicate sets\n", len(duplicatesB)-5)
			}
		}
	}
}

func main() {
	if len(os.Args) != 3 {
		fmt.Println("Usage: dircmp <directory_a> <directory_b>")
		fmt.Println()
		fmt.Println("Compares two directories and checks if they contain the exact same files")
		fmt.Println("(by content, regardless of file names or paths).")
		fmt.Println()
		fmt.Println("Returns:")
		fmt.Println("  - 'ok' if directories contain identical files")
		fmt.Println("  - 'fail' with a detailed report if there are discrepancies")
		os.Exit(1)
	}

	dirA := os.Args[1]
	dirB := os.Args[2]

	success, report, err := compareDirectories(dirA, dirB)
	if err != nil {
		fmt.Fprintf(os.Stderr, "\nError: %v\n", err)
		os.Exit(2)
	}

	printReport(success, report, dirA, dirB)

	if success {
		os.Exit(0)
	} else {
		os.Exit(1)
	}
}
