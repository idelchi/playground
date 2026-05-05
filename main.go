package main

import (
	"fmt"
	"os"
	"os/user"
	"strings"
)

func main() {
	USER := os.Getenv("USER")

	if usr, err := user.Current(); err == nil {
		if USER == "" {
			name := usr.Username
			if i := strings.LastIndex(name, `\`); i >= 0 {
				name = name[i+1:]
			}
			USER = name
		}
	}

	fmt.Println("-----------------------------")
	fmt.Printf("USER=%s\n", USER)
	fmt.Println("-----------------------------")
}
