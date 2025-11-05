// dircmp compares two directories by file content.
//
// Returns 'ok' if both directories contain identical files (regardless of names/paths).
// Returns 'fail' with detailed report if differences exist.
package main

import (
	"fmt"
	"os"

	"gitlab.garfield-labs.com/apps/dircmp/internal/cli"
)

var version = "dev"

func main() {
	if err := cli.New(version).Execute(); err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(2)
	}
}
