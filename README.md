# NTU CNS Final Project

## API

### Start API Server

Suppose the storage server is running on the same machine as your API server, and it is expecting gRPC requests via listening on port `8081`, then you will replace `ip:port` in the line below with `:8081`.

`go run API.go chunk.pb.go -server "ip:port"`

### Interact with API Server

Suppose the API server is running on the same machine as that of the client, the `curl` commands used to upload and download storage objects are listed below.

#### Upload API

`curl localhost:8080/upload?name=storage_object_name --data-binary @file_to_be_uploaded`

#### Download APi

`curl localhost:8080/download?name=storage_object_name > file_containing_downloaded_object`
