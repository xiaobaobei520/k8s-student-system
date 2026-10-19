import socket, struct, time, os

MACMAP = {
    "00:0c:29:67:58:b7": ("192.168.221.10", "k8s-master"),
    "00:0c:29:9b:94:f8": ("192.168.221.11", "k8s-node1"),
    "00:0c:29:5b:2d:fe": ("192.168.221.12", "k8s-node2"),
}
SERVER  = "192.168.221.1"
MASK    = "255.255.255.0"
ROUTER  = "192.168.221.2"
DNS     = ["192.168.221.2", "223.5.5.5"]
BCAST   = "192.168.221.255"
LOG     = r"D:\k8sstudey\ks\dhcp.log"

def ip2b(s):
    return socket.inet_aton(s)

def log(msg):
    line = "%s %s" % (time.strftime("%H:%M:%S"), msg)
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def build_reply(req, yiaddr, msgtype):
    xid, secs, flags = struct.unpack_from("!IHH", req, 4)
    chaddr = req[28:44]
    pkt  = struct.pack("!BBBB", 2, 1, 6, 0)
    pkt += struct.pack("!I", xid)
    pkt += struct.pack("!HH", 0, flags)
    pkt += ip2b("0.0.0.0")
    pkt += ip2b(yiaddr)
    pkt += ip2b("0.0.0.0")
    pkt += ip2b("0.0.0.0")
    pkt += chaddr          # chaddr 16 字节
    pkt += b"\x00" * 64    # sname
    pkt += b"\x00" * 128   # file
    pkt += b"\x63\x82\x53\x63"
    o  = bytes([53, 1, msgtype])
    o += bytes([54, 4]) + ip2b(SERVER)
    o += bytes([51, 4]) + struct.pack("!I", 3600)
    o += bytes([1, 4]) + ip2b(MASK)
    o += bytes([3, 4]) + ip2b(ROUTER)
    o += bytes([6, 4 * len(DNS)]) + b"".join(ip2b(d) for d in DNS)
    o += bytes([28, 4]) + ip2b(BCAST)
    o += bytes([15, 11]) + b"localdomain"
    o += bytes([255])
    return pkt + o

def parse_opts(pkt):
    i, out = 240, {}
    while i < len(pkt):
        c = pkt[i]
        if c == 255:
            break
        if c == 0:
            i += 1
            continue
        if i + 1 >= len(pkt):
            break
        l = pkt[i + 1]
        out[c] = pkt[i + 2:i + 2 + l]
        i += 2 + l
    return out

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
s.bind(("0.0.0.0", 67))
log("DHCP server listening on :67")

seen = {}
while True:
    try:
        data, addr = s.recvfrom(2048)
    except Exception as e:
        log("recv error: %s" % e)
        continue
    if len(data) < 240:
        continue
    mac = ":".join("%02x" % b for b in data[28:34])
    opts = parse_opts(data)
    mtype = opts.get(53, b"\x00")[0]
    if mac not in MACMAP:
        continue
    ip, name = MACMAP[mac]
    if mtype == 1:
        s.sendto(build_reply(data, ip, 2), (BCAST, 68))
        if seen.get(mac) != "offer":
            log("DISCOVER %s (%s) -> OFFER %s" % (mac, name, ip))
            seen[mac] = "offer"
    elif mtype == 3:
        s.sendto(build_reply(data, ip, 5), (BCAST, 68))
        if seen.get(mac) != "ack":
            log("REQUEST  %s (%s) -> ACK   %s" % (mac, name, ip))
            seen[mac] = "ack"
