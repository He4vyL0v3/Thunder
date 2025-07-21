from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from tqdm import tqdm

def is_proxy_working(proxy_dict, timeout=3):
    import requests

    proxy_str = None
    if "http" in proxy_dict:
        proxy_str = proxy_dict["http"].replace("http://", "")
    elif "https" in proxy_dict:
        proxy_str = proxy_dict["https"].replace("http://", "")
    else:
        return None

    api_url = "https://checkerproxy.net/api/checker"
    payload = {
        "proxy_list": proxy_str
    }

    try:
        resp = requests.post(api_url, data=payload, timeout=timeout)
        if resp.status_code == 200:
            result = resp.json()
            if isinstance(result, list) and result:
                proxy_info = result[0]
                if proxy_info.get("status") == "ok" or proxy_info.get("alive") is True:
                    return proxy_dict
        return None
    except Exception as e:
        print(f"Error proxy checking via API: {e}")
        return None

def get_proxies():
    import os

    proxy_file = "proxy_list.txt"
    if not os.path.exists(proxy_file):
        print(f"File {proxy_file} not found.")
        return []

    with open(proxy_file, "r") as f:
        lines = f.readlines()
    proxies_raw = set()
    for line in lines:
        proxy = line.strip()
        if proxy and ":" in proxy:
            proxies_raw.add(proxy)

    proxies_raw = list(proxies_raw)
    print("Loaded", len(proxies_raw), "proxies")

    if (len(proxies_raw)) != 0:
        proxies = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(is_proxy_working, {"http": f"http://{proxy}", "https": f"http://{proxy}"})
                for proxy in proxies_raw
            ]
            for future in tqdm(as_completed(futures), total=len(futures), desc="Checking proxies", unit="proxy"):
                result = future.result()
                if result:
                    proxies.append(result)

        print(f"Working proxies: {len(proxies)}")
        return proxies
    return None

if __name__ == "__main__":
    proxies = get_proxies()
