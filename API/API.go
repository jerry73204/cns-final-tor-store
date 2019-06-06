//go:generate protoc --proto_path=.. --go_out=plugins=grpc:. ../chunk.proto
package main

import (
	"bytes"
	"context"
	"errors"
	"flag"
	"fmt"
	"io"
	"io/ioutil"
	"log"
	"net/http"
	"sort"
	"sync"
	"time"

	"github.com/golang/protobuf/ptypes/empty"
	"google.golang.org/grpc"
)

const (
	port           = 8080
	timeout        = 10
	nameParamKey   = "name"
	lackNameErrStr = "Specify %s=theNameYouWant as an URL param"
)

var (
	name2Keys map[string][]*Chunk
	mx        sync.RWMutex
	globalCC  *grpc.ClientConn
)

func main() {
	addr := flag.String("server", "localhost:8081", "the addr of the storage server")
	flag.Parse()

	fmt.Printf("Connecting to storage server at %s\n", *addr)
	var err error
	globalCC, err = grpc.Dial(*addr,
		grpc.WithInsecure(),
		grpc.WithBlock(),
		grpc.WithTimeout(time.Second*timeout),
	)
	if err != nil {
		log.Fatalln(err)
	}

	fmt.Printf("Starting API server at port %d\n", port)
	http.HandleFunc("/upload", uploadEndpoint)
	http.HandleFunc("/download", downloadEndpoint)
	log.Fatal(http.ListenAndServe(fmt.Sprintf(":%d", port), nil))
}

func uploadEndpoint(w http.ResponseWriter, req *http.Request) {
	name, ok := getName(w, req)
	if !ok {
		return
	}

	bs, err := ioutil.ReadAll(req.Body)
	if err != nil {
		writeErr(w, http.StatusInternalServerError, err)
		return
	}

	keys, err := upload(globalCC, bs)
	if err != nil {
		writeErr(w, http.StatusInternalServerError, err)
		return
	}

	store(name, keys)
}

func upload(cc *grpc.ClientConn, bs []byte) ([]*Chunk, error) {
	client := NewStorageClient(cc)

	sizeWrapper, err := client.GetChunkSize(context.Background(), &empty.Empty{})
	if err != nil {
		return nil, err
	}

	size := int(sizeWrapper.GetValue())
	if size == 0 {
		return nil, errors.New("Chunk size cannot be zero")
	}

	stream, err := client.Upload(context.Background())
	if err != nil {
		return nil, err
	}

	errCh := make(chan error)

	go func() {
		defer stream.CloseSend()
		for L := 0; L < len(bs); L += size {
			R := min(L+size, len(bs))
			err := stream.Send(&Chunk{
				Idx:  int32(L / size),
				Data: bs[L:R],
			})
			if err != nil {
				errCh <- err
				return
			}
		}
	}()

	done := make(chan struct{})
	keys := make([]*Chunk, 0, len(bs)/size+1)
	go func() {
		for {
			key, err := stream.Recv()
			if err == io.EOF {
				close(done)
				return
			}
			if err != nil {
				errCh <- err
				return
			}
			keys = append(keys, key)
		}
	}()

	select {
	case err := <-errCh:
		return nil, err
	case <-done:
		return keys, nil
	}
}

func downloadEndpoint(w http.ResponseWriter, req *http.Request) {
	name, ok := getName(w, req)
	if !ok {
		return
	}

	keys, ok := load(name)
	if !ok {
		writeErr(w, http.StatusNotFound,
			errors.New(fmt.Sprintf("%s has not been uploaded before", name)),
		)
		return
	}

	vals, err := download(globalCC, keys)
	if err != nil {
		writeErr(w, http.StatusInternalServerError, err)
		return
	}

	bs, err := vals2Bytes(vals)
	if err != nil {
		writeErr(w, http.StatusInternalServerError, err)
		return
	}

	_, err = w.Write(bs)
	if err != nil {
		writeErr(w, http.StatusInternalServerError, err)
		return
	}
}

func download(cc *grpc.ClientConn, keys []*Chunk) ([]*Chunk, error) {
	client := NewStorageClient(cc)

	stream, err := client.Download(context.Background())
	if err != nil {
		return nil, err
	}

	errCh := make(chan error)
	go func() {
		defer stream.CloseSend()
		for _, key := range keys {
			err := stream.Send(key)
			if err != nil {
				errCh <- err
				return
			}
		}
	}()

	vals := make([]*Chunk, 0, len(keys))
	done := make(chan struct{})
	go func() {
		for {
			val, err := stream.Recv()
			if err == io.EOF {
				close(done)
				return
			}
			if err != nil {
				errCh <- err
				return
			}
			vals = append(vals, val)
		}
	}()

	select {
	case err := <-errCh:
		return nil, err
	case <-done:
		return vals, nil
	}
}

func vals2Bytes(vals []*Chunk) ([]byte, error) {
	sort.Slice(vals, func(i, j int) bool { return vals[i].Idx < vals[j].Idx })

	var b bytes.Buffer
	for _, val := range vals {
		_, err := b.Write(val.Data)
		if err != nil {
			return nil, err
		}
	}

	return b.Bytes(), nil
}

func writeErr(w http.ResponseWriter, code int, err error) {
	w.WriteHeader(code)
	if _, err = io.WriteString(w, err.Error()); err != nil {
		log.Println(err)
	}
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

func store(name string, keys []*Chunk) {
	defer mx.Unlock()
	mx.Lock()
	name2Keys[name] = keys
}

func load(name string) (keys []*Chunk, ok bool) {
	defer mx.RUnlock()
	mx.RLock()
	keys, ok = name2Keys[name]
	return
}

func getName(w http.ResponseWriter, req *http.Request) (string, bool) {
	names, ok := req.URL.Query()[nameParamKey]
	if !ok {
		writeErr(w, http.StatusBadRequest,
			errors.New(
				fmt.Sprintf(lackNameErrStr, nameParamKey),
			),
		)
		return "", false
	}
	return names[0], true
}
