package cli

import (
	"fmt"
	"os"

	"github.com/MakeNowJust/heredoc/v2"
	"github.com/spf13/cobra"

	"gitlab.garfield-labs.com/apps/dircmp/internal/dircmp"
)

// CLI represents the command-line interface.
type CLI struct {
	version string
}

// Options represents the CLI options.
type Options struct {
	// Verbose indicates whether verbose output is enabled.
	Verbose bool
}

// New creates a new CLI instance with the given version.
func New(version string) CLI {
	return CLI{version: version}
}

// Execute runs the CLI with the provided arguments.
func (c CLI) Execute() error {
	var opts Options

	cmd := &cobra.Command{
		Use:   "dircmp [flags] <dir_a> <dir_b>",
		Short: "Compare two directories by file content",
		Long: heredoc.Doc(`
			Compares two directories by file content.
		`),
		Version: c.version,
		Args:    cobra.ExactArgs(2),
		RunE: func(cmd *cobra.Command, args []string) error {
			return run(args[0], args[1], &opts)
		},
		SilenceErrors: true,
	}

	cmd.Flags().BoolVarP(&opts.Verbose, "verbose", "v", false, "Show verbose output")

	cmd.Flags().SortFlags = false

	return cmd.Execute() //nolint:wrapcheck // Error does not need additional wrapping.
}

// run executes the directory comparison logic.
func run(dirA, dirB string, opts *Options) error {
	logger := Logger{Verbose: opts.Verbose}

	logger.Printlnf("Scanning %s...", dirA)

	scanA, err := dircmp.Dir(dirA, logger)
	if err != nil {
		return fmt.Errorf("scanning %s: %w", dirA, err)
	}

	logger.Printlnf("Found %d files (%d unique) in %s", scanA.TotalFiles, len(scanA.HashCounts), dirA)

	logger.Printlnf("Scanning %s...", dirB)

	scanB, err := dircmp.Dir(dirB, logger)
	if err != nil {
		return fmt.Errorf("scanning %s: %w", dirB, err)
	}

	logger.Printlnf("Found %d files (%d unique) in %s", scanB.TotalFiles, len(scanB.HashCounts), dirB)

	if !dircmp.Compare(dirA, dirB, scanA, scanB) {
		os.Exit(1)
	}

	return nil
}
