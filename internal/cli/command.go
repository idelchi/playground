package cli

import (
	"fmt"
	"os"

	"github.com/spf13/cobra"
	"gitlab.garfield-labs.com/apps/dircmp/internal/dircmp"
)

// CLI wraps the command-line interface.
type CLI struct {
	version string
}

// Options holds all command-line flags.
type Options struct {
	Verbose bool
}

// New creates a new CLI instance.
func New(version string) *CLI {
	return &CLI{version: version}
}

// Execute runs the CLI application.
func (c *CLI) Execute() error {
	var opts Options

	cmd := &cobra.Command{
		Use:     "dircmp <dir_a> <dir_b>",
		Short:   "Compare two directories by content",
		Long:    "Compares two directories by file content.\nReturns 'ok' if both contain identical files (regardless of names/paths).\nReturns 'fail' with detailed report if differences exist.",
		Version: c.version,
		Args:    cobra.ExactArgs(2),
		RunE: func(cmd *cobra.Command, args []string) error {
			return run(args[0], args[1], &opts)
		},
		SilenceUsage:  true,
		SilenceErrors: true,
	}

	// Define flags
	cmd.Flags().BoolVarP(&opts.Verbose, "verbose", "v", false, "enable verbose output")

	return cmd.Execute()
}

// run executes the directory comparison.
func run(dirA, dirB string, opts *Options) error {
	logger := &Logger{Verbose: opts.Verbose}

	// Scan both directories
	logger.Logf("Scanning %s...", dirA)
	scanA, err := dircmp.Dir(dirA, logger)
	if err != nil {
		return fmt.Errorf("error scanning %s: %w", dirA, err)
	}
	logger.Logf("Found %d files (%d unique) in %s", scanA.TotalFiles, len(scanA.HashCounts), dirA)

	logger.Logf("Scanning %s...", dirB)
	scanB, err := dircmp.Dir(dirB, logger)
	if err != nil {
		return fmt.Errorf("error scanning %s: %w", dirB, err)
	}
	logger.Logf("Found %d files (%d unique) in %s", scanB.TotalFiles, len(scanB.HashCounts), dirB)

	// Compare and report
	if !dircmp.Compare(dirA, dirB, scanA, scanB) {
		os.Exit(1)
	}

	return nil
}
