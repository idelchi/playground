package dircmp

import (
	"fmt"
	"sort"
	"strings"
)

// Compare compares two directory scans and prints results.
// Returns true if directories match, false otherwise.
func Compare(dirA, dirB string, scanA, scanB *Scan) bool {
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

// computeDiff computes the difference between two scans.
func computeDiff(scanA, scanB *Scan) Diff {
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

// reportDiff prints a detailed difference report.
func reportDiff(diff Diff, scanA, scanB *Scan) {
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

		for i := range limit {
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

		for i := range limit {
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

// showDuplicates shows information about duplicates and different paths.
func showDuplicates(scanA, scanB *Scan) {
	var (
		duplicatesA, duplicatesB []string
		differentPaths           []string
	)

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

// pathsEqual checks if two path lists are equal (order-independent).
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

// sortedKeys returns sorted keys from a map.
func sortedKeys(m map[string]int) []string {
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}

	sort.Strings(keys)

	return keys
}
