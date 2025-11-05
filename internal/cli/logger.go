package cli

import (
	"fmt"
	"os"
)

// Logger handles conditional output based on verbosity.
type Logger struct {
	Verbose bool
}

// Logf prints a formatted message to stderr if Verbose is true.
func (l *Logger) Logf(format string, args ...interface{}) {
	if l.Verbose {
		fmt.Fprintf(os.Stderr, format+"\n", args...)
	}
}
