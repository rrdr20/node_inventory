# Server Status
As my homelab expands I have been using various tools to monitor and collect data. All of these tools work as expected
and I have a stable solution. Currently my lab runs Kubernetes as a bare metal deployment which takes quite of bit of
extra work to get running. Although the lab is small each node is treated as ephemeral to simulate the larger datacenter
deployments. In an effort to automate the bootstrapping of nodes I wanted a custom way to collect the resources that are
deployed on each host.

## Python
The first solution for collecting node resource inventory was writen in Python. It works fine for the the collection of
some basic information and requires Python and libraries to be installed all of which would have be baked into the base
deployment image.

* [Code](python)

## Go
As I am converting more applications to Go I have decided to attempt a verion of the node resource inventory.

* [Code](go)
