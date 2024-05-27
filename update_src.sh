#!/bin/bash

# Extract IPv6 address
new_ipv6_prefix=$(curl --tftp-blksize 64 --tftp-no-options tftp://192.168.16.1/hip6.txt)

gw_addr=fe80::186f:77ff:fec5:6c86
host_if=eth2
table_id=3462

self_suffix=123
prefix_len=112

tun_type=ip6gre
tun_name=gre6-stuix
tun_mtu=1448
api_endpoint='admin:password@[2400:1b85:637b::1234]:16581/update_endpoint_ip'

# Check if IPv6 address is found
if [ -z "$new_ipv6_prefix" ]; then
    echo "Error: No IPv6 address found."
    exit 1
fi

new_ipv6_addr="${new_ipv6_prefix}${self_suffix}"
new_ipv6_net="${new_ipv6_prefix}${self_suffix}/${prefix_len}"

set -x
set -e
current_gre_local=$(ip -json -d link show $tun_name | jq -r '.[].linkinfo.info_data | .local')

if [ "$new_ipv6_addr" = "$current_gre_local" ]; then
    echo "nochg"
    timeout 10 curl -k --interface "$new_ipv6_addr" -X POST -d "$new_ipv6_addr" "https://$api_endpoint"
    exit 0
fi

# Flush the ip rule based on new IPv6 address read from interface
ip -6 addr flush dev $host_if
ip -6 addr add $new_ipv6_net dev $host_if
ip -6 route add default via $gw_addr dev $host_if table $table_id || true
ip -6 route replace default via $gw_addr dev $host_if table $table_id || true
ip -6 rule del table $table_id || true
ip -6 rule add from "$new_ipv6_addr" lookup $table_id

# Update local address of tunnel
ip link set $tun_name type $tun_type local "$new_ipv6_addr"
ip link set $tun_name mtu $tun_mtu

# Post the address to remote server
timeout 10 curl -k --interface "$new_ipv6_addr" -X POST -d "$new_ipv6_addr" "https://$api_endpoint"