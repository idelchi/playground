package main

import (
	"fmt"
	"os"
	"os/user"
	"path/filepath"
)

func main() {
	fmt.Println("-----------------------------")
	fmt.Printf("USER=%s\n", os.Getenv("USER"))
	fmt.Printf("USERNAME=%s\n", os.Getenv("USERNAME"))
	fmt.Printf("HOME=%s\n", filepath.ToSlash(os.Getenv("HOME")))

	fmt.Println("-----------------------------")

	usr, _ := user.Current()
	fmt.Printf("user.Name=%s\n", usr.Name)

	fmt.Printf("user.Username=%s\n", usr.Username)

	fmt.Printf("user.HomeDir=%s\n", filepath.ToSlash(usr.HomeDir))

	fmt.Println("-----------------------------")

}
