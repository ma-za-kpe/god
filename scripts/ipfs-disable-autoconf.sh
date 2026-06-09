#!/bin/sh
# Private swarm configuration for Kubo v0.29.0+
# Use '|| true' on each line so unknown config keys don't crash the init.
set -e

ipfs config --json AutoConf.Enabled false
ipfs config --json Bootstrap '[]'
ipfs config --json Routing.DelegatedRouters '[]' || true
ipfs config --json Ipns.DelegatedPublishers '[]' || true
ipfs config --json DNS.Resolvers '{}' || true
ipfs config --json Swarm.Transports.Network.Websocket false || true
ipfs config --json Swarm.Transports.Network.QUIC false || true
ipfs config --json AutoTLS.Enabled false || true
# Clear server-profile address filters so Docker-internal IPs (172.20.x.x) aren't blocked
ipfs config --json Swarm.AddrFilters '[]'

echo "Private swarm configuration applied."
