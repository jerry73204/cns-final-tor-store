package main

import (
	"fmt"
	"io/ioutil"
	"log"
	"net/http"
)

var data []byte

func main() {
	http.HandleFunc("/upload", upload)
	http.HandleFunc("/download", download)
	log.Fatal(http.ListenAndServe(":8080", nil))
}

func printHeader(header map[string][]string) {
	for key, vals := range header {
		fmt.Printf("%s: %v\n", key, vals)
	}
}

func upload(w http.ResponseWriter, req *http.Request) {
	bs, err := ioutil.ReadAll(req.Body)
	if err != nil {
		log.Println(err)
	}

	data = bs
}

func download(w http.ResponseWriter, req *http.Request) {
	_, err := w.Write(data)
	if err != nil {
		log.Println(err)
	}
}
