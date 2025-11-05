package dircmp

import (
	"crypto/sha256"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"runtime"
	"sync"
	"sync/atomic"

	"github.com/charlievieth/fastwalk"
)

// Logger represents the interface for progress reporting.
type Logger interface {
	Printlnf(format string, args ...any)
}

// fileJob represents a file to be hashed.
type fileJob struct {
	path    string
	relPath string
	size    int64
}

// fileResult represents a hashed file result.
type fileResult struct {
	hash    string
	relPath string
	size    int64
}

// bufPool is a buffer pool to reduce memory allocations during file hashing.
//
//nolint:gochecknoglobals // This is a shared pool for performance.
var bufPool = sync.Pool{
	New: func() any {
		b := make([]byte, 32*1024) // 32KB buffer.

		return &b
	},
}

// hashFile computes the SHA256 hash of a file using a pooled buffer.
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

// Dir scans a directory recursively and computes file hashes concurrently.
func Dir(dir string, logger Logger) (*Scan, error) {
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

	numWorkers := runtime.NumCPU()
	logger.Printlnf("Using %d workers for hashing", numWorkers)

	jobs := make(chan fileJob, numWorkers*2)
	results := make(chan fileResult, numWorkers*2)

	var (
		wg                      sync.WaitGroup
		filesFound, filesHashed atomic.Int64
	)

	// Start worker goroutines.

	for range numWorkers {
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
				if hashed%100 == 0 {
					logger.Printlnf("Hashed %d files...", hashed)
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
	scan := &Scan{
		Files:       []File{},
		HashCounts:  make(map[string]int),
		HashToFiles: make(map[string][]string),
	}

	var (
		mu        sync.Mutex
		collectWg sync.WaitGroup
	)

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
		if found%1000 == 0 {
			logger.Printlnf("Found %d files...", found)
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
