# TorFS: Abusing Tor's Onion service to store data

## Authors

* __Arthur Wang__, __Hsiang-Jui Lin__: Tor Onion service storage and virtual file system
* __Hsing-Yu Chen__: Data block API
* __Adrien Wu__, __Yang Han Li__: Reports and documentation

## About this project

The TorFS project was initialted as a final project in [NTU Cryptography and Network Security course](https://www.csie.ntu.edu.tw/~hchsiao/courses/cns19.html). It was motivated by [dnsfs](https://github.com/benjojo/dnsfs) and [pingfs](https://github.com/yarrick/pingfs). We explored the similar idea, that exploits storage from protocols which was not intended for this purpose. We discovered Tor hidden services can be regarded as reliable and retrievable data storage.

## How TorFS works

Before involving into TorFS, it's better to understand Onion services (formerly, hidden services). It provides anonymity to websites and other services beneath Tor's Onion network. Tor website already has a good [explanation](https://www.torproject.org/docs/onion-services.html.en) on Onion services. For those who wants to know about it deserve 10 minutes reading on this.

To setup an Onion service, we generate a private/public long-term key pair as our service indentity. Currently Tor allows Ed25519 or RSA1024 keys. We advertise our service named XYZ.onion or some by asking _introduction points_, basically Tor relays, to store our public keys. Whoever client visiting our service should learn about our public key, and setups up a _rendezvous point_ for futher contact.

However. we only need to store data without an actual service. We don't need the whole feature of Onion service.  It turns out the _introduction points_, along with our public keys, can survive even the actual service is absent. As you can figure out, we put the stuffs into public keys and retrieve them back using _.onion_ addresses! That's basically how TorFS works.

In details, e derived an algorithm to generate 1024-bit long RSA keys, where 800 of 1024-bits of _n_ component (product of two primes) is arbitrary data. We manipulate remaining bits to satisfy RSA's constraints. Then, We build a virtual file system that slice the files into 800-bit blocks, distribute them to introduction points, and keep track of the replicas by _.onion_ addresses.

## Prerequisites

Since the our code uses async features, it requires Python 3.7 minimum.

Install depent pacakges using `pip` or other package manager:

```sh
pip3 install -r requirements.txt
```

Make sure you start the Tor daemon and [configure](https://www.torproject.org/docs/tor-onion-service.html.en) it to allow Onion services.

## Demo usage

Run `python3 ./src/main.py` to start TorFS shell.

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
