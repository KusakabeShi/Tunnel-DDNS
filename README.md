# Tunnel-DDNS

客戶端: 每分鐘呼叫 API
伺服器: 收 API，改 tunnel remote address

假設:

伺服器IP: `2400:1b85:637b::1234/64`  
伺服器上面的路由(隧道專用): `2400:1b85:637b::1 via ens18`

客戶端IP: `fda8:989f:eff5::ffff/64`  
伺服器上面的路由(隧道專用): `fe80::b438:4f31 via eth2`

## 伺服器

幫 `ens18` 設定 `ip rule`:
```ifupdown
iface ens18 inet6 static
    address 2400:1b85:637b::1234/64
    post-up ip -6 r a default via 2400:1b85:637b::1 dev $IFACE metric 1 table 18041
    post-up ip -6 rule add from 2400:1b85:637b::1234/128 lookup 18041
```

設定 gre/vxlan 隧道:  
要安裝 tmux ，API server 跑在 tmux 裡面

```ifupdown
auto gre6-kskbix
iface gre6-kskbix inet6 static
    pre-up    ip link add $IFACE type ip6gre remote fda8:989f:eff5::ffff local 2400:1b85:637b::1234
    #pre-up    ip link add $IFACE type vxlan remote fda8:989f:eff5::ffff local 2400:1b85:637b::1234 id 215842 dstport 4789
    post-down ip link del $IFACE
    post-up ip link set dev $IFACE mtu 1448
    post-up tmux new -d -s update_$IFACE
    post-up tmux send-keys -t update_$IFACE "python3 /root/update_tun_ssl.py -t $IFACE -T ip6gre"
    post-up tmux send-keys -t update_$IFACE Enter
    post-down tmux kill-session -t update_$IFACE || true
    address fe80::eff5:3bd9/64
```

`update_tun_ssl.py` 在另外一個檔案 ，放到 `/root/update_tun_ssl.py`

## 客戶端

幫 `eth2` 設定 `ip rule`:
```ifupdown
iface eth2 inet6 static
    address fda8:989f:eff5::ffff/64
    post-up ip -6 r a default via fe80::b438:4f31 dev $IFACE table 3462
    post-up ip -6 rule add from fda8:989f:eff5::ffff/128 lookup 3462
```

設定 gre/vxlan 隧道:

```ifupdown
auto gre6-stuix
iface gre6-stuix inet6 static
    address fe80::053a:9115/64
    pre-up    ip link add $IFACE type ip6gre local fda8:989f:eff5::ffff remote 2400:1b85:637b::1234 dev eth2
    #pre-up    ip link add $IFACE type vxlan local fda8:989f:eff5::ffff remote 2400:1b85:637b::1234 dev eth2 id 200101 dstport 4789
    post-down ip link del $IFACE
    post-up ip link set dev $IFACE mtu 1448
```


更新腳本:
放在 crontab 每分鐘執行一次

```bash
#!/bin/bash

# Extract IPv6 address
ipv6_address=$(ip -6 addr show eth2 | awk '/inet6/ && !/deprecated/ && !/fe80/ {print $2}' | cut -d'/' -f1)

# Check if IPv6 address is found
if [ -z "$ipv6_address" ]; then
    echo "Error: No IPv6 address found."
    exit 1
fi
set -x

# Flush the ip rule based on new IPv6 address read from interface
ip -6 rule del table 3462 || true
ip -6 rule add from "$ipv6_address" lookup 3462

# Update local address of tunnel "gre-up"
ip link set gre6-stuix type ip6gre local "$ipv6_address"
ip link set gre6-stuix mtu 1448

# Post the address to remote server
timeout 10 curl -k --interface "$ipv6_address" -X POST -d myip https://admin:password@[2400:1b85:637b::1234]:16581/update_endpoint_ip
```
