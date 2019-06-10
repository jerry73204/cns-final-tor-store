# TorFS: Abusing Tor Onion service to store data

## Authors

* __Arthur Wang__, __Hsiang-Jui Lin__: Tor hidden service storage and virtual file system
* __Hsing-Yu Chen__: Data block API
* __Adrien Wu__, __Yang Han Li__: Reports and documentation

## About this project

The TorFS project was initialted as a final project in [NTU Cryptography and Network Security course](https://www.csie.ntu.edu.tw/~hchsiao/courses/cns19.html). It was motivated by [dnsfs](https://github.com/benjojo/dnsfs) and [pingfs](https://github.com/yarrick/pingfs). We explored similar idea, that exploits storage from protocols which was not intended for this purpose, and discovered Tor hidden services can be regarded as reliable data storage.

## How TorFS works

To know about how TorFS works, we have to understand Onion services (formerly, hidden services). It provides anonymity to websites and other services beneath Tor's Onion network. Tor website already has a good [introduction](https://www.torproject.org/docs/onion-services.html.en). It deserves 10 minutes reading.

To setup an Onion service, we generate a private/public long-term key pair for our service. Currently it allows Ed25519 or RSA1024 keys. We then advertise our service, named XYZ.onion or some. Tor does so by asking _introduction points_, basically Tor relays, to store our public keys. Whoever client visiting our service should learn about our public key, and setups up a _rendezvous point_.

We have to make a stop here. We only need to store data without an actual service. It turns out the _introduction points_, along with our public key, can survive even the actual service is absent. As you can figure out, we put the stuffs into public keys and retrieve them back using _.onion_ addresses! That's basically how TorFS works.

To state in details, we derived an algorithm to generate 1024-bit long RSA keys, 800 of 1024-bits is arbitrary data in the _n_ component (product of two primes). We manipulate remaining bits to satisfy RSA's constraints. We build a virtual file system that slice the files into 800-bit blocks, and map the replicas into _.onion_ addresses.

## Demo usage

Since the our code uses async features, it requires Python 3.7 minimum.

Install depent pacakges using `pip` or other package manager:

```sh
pip3 install -r requirements.txt
```

You can start a TorFS shell by `python3 ./src/main.py`.

```
torfs> help                        # Ask help to learn about command usages
torfs> cp @demo/demo.jpg demo.jpg  # Upload our demo.jpg to Tor network
torfs> ls .                        # List directory in virtual fs
demo.jpg
torfs> cp demo.jpg @demo_copy.jpg  # Download the file back
torfs> exit
```

Following the demo above, we expect identical file contents.

```
$ sha256sum demo_copy.jpg demo/demo.jpg
b053f4e17afa4c40d54fbf24caf5702e2db0935ee71f5333991b29da94de07d8  demo_copy.jpg
b053f4e17afa4c40d54fbf24caf5702e2db0935ee71f5333991b29da94de07d8  demo/demo.jpg
```

## Disclaimer

* The project is intended to as a proof-of-concept and for educational purpose. Do NOT distribute it for malicious means.
* We have limited time to complete our project. The code is not guaranteed to be bug-free, and thus not suggested for production use.

## License

MIT
