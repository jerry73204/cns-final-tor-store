package main

import (
	"bytes"
	"crypto/sha256"
	"io"
	"log"
	"math/rand"
	"net"
	"testing"
	"time"

	empty "github.com/golang/protobuf/ptypes/empty"
	wrappers "github.com/golang/protobuf/ptypes/wrappers"
	context "golang.org/x/net/context"
	"google.golang.org/grpc"
	"google.golang.org/grpc/test/bufconn"
)

const bufSize = 1024 * 1024

var lis *bufconn.Listener

func init() {
	lis = bufconn.Listen(bufSize)
	s := grpc.NewServer()
	RegisterStorageServer(s, newServer())
	go func() {
		if err := s.Serve(lis); err != nil {
			log.Fatalf("Server exited with error: %v", err)
		}
	}()
}

func bufDialer(string, time.Duration) (net.Conn, error) {
	return lis.Dial()
}

type server struct {
	m map[string][]byte
}

func newServer() *server {
	return &server{m: make(map[string][]byte)}
}

func (s *server) GetChunkSize(ctx context.Context, void *empty.Empty) (
	*wrappers.Int32Value, error) {
	return &wrappers.Int32Value{Value: 128}, nil
}

func (s *server) Upload(stream Storage_UploadServer) error {
	for {
		val, err := stream.Recv()
		if err == io.EOF {
			return nil
		}
		if err != nil {
			log.Fatalln(err)
		}

		key := sha256.Sum256(val.Data)
		s.m[string(key[:])] = val.Data

		err = stream.Send(&Chunk{Idx: val.Idx, Data: key[:]})
		if err != nil {
			log.Fatalln(err)
		}
	}
}

func (s *server) Download(stream Storage_DownloadServer) error {
	for {
		key, err := stream.Recv()
		if err == io.EOF {
			return nil
		}
		if err != nil {
			log.Fatalln(err)
		}

		k := string(key.Data)
		val, ok := s.m[k]
		if !ok {
			log.Fatalf("%s does not exist in map\n", k)
		}

		err = stream.Send(&Chunk{Idx: key.Idx, Data: val})
		if err != nil {
			log.Fatalln(err)
		}
	}
}

func TestAll(t *testing.T) {
	cc, err := grpc.Dial("bufnet", grpc.WithDialer(bufDialer), grpc.WithInsecure())
	if err != nil {
		t.Fatalf("Failed to dial bufnet: %v", err)
	}
	defer cc.Close()

	in := make([]byte, 4096)
	rand.Read(in)

	keys, err := upload(cc, in)
	if err != nil {
		t.Fatal(err)
	}

	vals, err := download(cc, keys)
	if err != nil {
		t.Fatal(err)
	}

	// simulate the out-of-order scenario
	rand.Seed(time.Now().UnixNano())
	rand.Shuffle(len(vals), func(i, j int) { vals[i], vals[j] = vals[j], vals[i] })

	out, err := vals2Bytes(vals)
	if err != nil {
		t.Fatal(err)
	}

	if !bytes.Equal(in, out) {
		t.Fatal("in and out are not equal\n")
	}
}
