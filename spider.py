import urllib3
import requests
import os
import time
import threading
from Crypto.Cipher import AES
from bs4 import BeautifulSoup

urllib3.disable_warnings()

site_url = "https://jable.tv/videos/abp-984/"
request_header = {
    "authority": "tggfk0.cdnlab.live",
    "method": "GET",
    "scheme": "https",
    "accept": "*/*",
    "accept-encoding": "gzip, deflate, br",
    "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
    "origin": "https://jable.tv",
    "referer": "https://jable.tv/",
    "sec-ch-ua": "'Chromium';v='88', 'Google Chrome';v='88', ';Not A Brand';v='99'",
    "sec-ch-ua-mobile": "?0",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "cross-site",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.96 Safari/537.36",
}


def clear():
    clear_cmd = r'find . -name "*" -type f -size 0c | xargs -n 1 rm -f' # clear empty files which are probably the failed ones in last session
    os.system(clear_cmd)


def get_download_url(site_url):
    html = requests.get(headers=request_header, url=site_url)
    soup = BeautifulSoup(html.text, 'lxml')
    out_links = soup.find_all("link")
    download_url = ""
    for d in out_links:
        if "m3u8" in d.get("href"):
            download_url = d.get("href")
            break
    m3u8_file = download_url.split("/")[-1]
    download_url = download_url[:download_url.find(m3u8_file)]
    return download_url, m3u8_file


def download_m3u8(download_url, m3u8_file):
    try:
        m3u8_url = download_url + m3u8_file
        m3u8_raw = requests.get(headers=request_header, url=m3u8_url)
        open(m3u8_file, "wb").write(m3u8_raw.content)
    except Exception as e:
        print("[*] Exception: ", e)
        return -1
    return m3u8_file
    

def download_key(download_url, key_file):
    key_url = download_url + key_file.decode()
    print("[*] Key Url is:", key_url)
    try:
        raw_key = requests.get(headers=request_header, url=key_url)
        assert len(raw_key.content) == 16
        open(key_file, "wb").write(raw_key.content)
    except Exception as e:
        print("[*] Exception: ", e)
        return -1
    return len(raw_key.content)


def get_chunk_from_m3u8(m3u8_file):
    cipher_suite = []
    ts_file_set = []
    for i in range(0, len(m3u8_file) - 1):
        line = m3u8_file[i]
        if b"#EXT-X-KEY" in line:
            key_url_start = line.find(b",URI")
            iv_start = line.find(b",IV")
            method = line[:key_url_start].split(b"=")[1]
            iv = line[iv_start:].split(b"=")[1]
            key_path = line[key_url_start : iv_start].split(b"=")[1].strip(b'"')
            cipher_suite = [key_path, method, iv]
        if b"#EXTINF" in line:
            ts_file_set = m3u8_file[i:-1]
            break
    return cipher_suite, ts_file_set
    

def get_ts_urls_from_m3u8(m3u8_ts_content):
    ts_urls = []
    for i in range(1, len(m3u8_ts_content), 2):
        ts_urls.append(m3u8_ts_content[i][:-1])
    return ts_urls


def get_key_from_file(cipher_suites, download_url):
    print("[*] Start to crawling for AES key")
    if not download_key(download_url, cipher_suites[0]):
        print("[*] Error while downloading the key")
    raw_key = open(cipher_suites[0],"rb").read()
    print("[*] Get AES key: ", raw_key)
    iv = bytes.fromhex(cipher_suites[2][2:-1].decode())
    assert len(iv) == 16
    print("[*] Get AES iv:" , len(iv))

    return [raw_key, iv]


def get_ts_content(ts_urls, cipher, download_url):
    print("[*] Start to Download...")
    for ts in ts_urls:
        ts_download_url = download_url + ts.decode()
        res = requests.get(headers = request_header, url=ts_download_url, stream=True)
        print("\t[.] Response:", res.status_code)
        with open(b"video/" + ts,"wb+") as file:
            decrypted_chunk = cipher.decrypt(res.content)
            file.write(decrypted_chunk)
                        
    
def multi_download(download_url, ts_urls, keys, num_thread=8):
    downloaded_list = os.listdir('video/')
    downloaded_list = list(map(lambda x : x.encode(), downloaded_list))
    trying_list = list(set(ts_urls) - set(downloaded_list))
    ts_size = len(trying_list)
    print("Need to Download %d ts file" % ts_size)
    chunk = ts_size // num_thread
    thread_list = []
    cipher = AES.new(keys[0], AES.MODE_CBC, keys[1])
    print("[*] Splitting Threading Chunk.")
    for i in range(num_thread):
        start = chunk * i
        if i == num_thread - 1:
            end = ts_size
        else:
            end = start + chunk
        print("\t", start, end)
        t = threading.Thread(target=get_ts_content, kwargs={"ts_urls":trying_list[start:end], "cipher":cipher,"download_url": download_url})
        t.setDaemon(True)
        t.start()
        thread_list.append(t)
    print("[*] Begin to Multi-thread Download..")
    for t in thread_list:
        t.join()
    print("[*] Downloading Success")


def preprocess(download_url, m3u8_file):
    m3u8_content = open(m3u8_file, "rb").readlines()
    cipher_suite, ts_content = get_chunk_from_m3u8(m3u8_content)
    ts_urls = get_ts_urls_from_m3u8(ts_content)

    key_materials = get_key_from_file(cipher_suite, download_url)
    return key_materials, ts_urls 


def merge_ts(working_dir, ts_file):
    os.chdir(working_dir)
    ts_file_ordered = b' '.join(ts_file)
    merge_cmd = "cat " + ts_file_ordered.decode() + " > final.ts"
    os.system(merge_cmd)
    convert_cmd = "ffmpeg -i final.ts -c copy -bsf:a aac_adtstoasc final.mp4"
    os.system(convert_cmd)

def wrap_up():
    clear()
    download_url, m3u8_file = get_download_url(site_url)
    print("[*] Downloading url is: ", download_url)
    if download_m3u8(download_url, m3u8_file) == -1:
        print("[*] Error while downloading the m3u8 file")
    print("[*] Downloading m3u8 file %s success." % m3u8_file)
    keys, tss = preprocess(download_url, m3u8_file)
    print(keys, len(tss))
    multi_download(download_url, tss, keys)
    merge_ts("video/", tss)


wrap_up()
