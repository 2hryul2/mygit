FLUSH_PKT = b"0000"


def pkt_line(data: bytes) -> bytes:
    total = len(data) + 4
    if total > 65520:
        raise ValueError(f"pkt-line too long: {total} bytes")
    return f"{total:04x}".encode("ascii") + data
