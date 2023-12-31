# pip3 install cairosvg img2pdf pyTelegramBotAPI asyncer sentry-sdk
from asyncer import asyncify
from math import ceil
import zipfile
import os
import threading
from cairosvg import svg2png
import cairosvg
import io
import img2pdf
# from time import sleep
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
import requests
import sys

session = requests.Session()
session.headers.update({"user-agent": 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36'})

MEDIUM_QUALITY = (1.0, 150)
MEDIUM_PLUS_QUALITY = (2, 300)


def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


# Thanks to Alexandra Zaharia: https://alexandra-zaharia.github.io/posts/how-to-return-a-result-from-a-python-thread/
class ReturnValueThread(threading.Thread):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.result = None

    def run(self):
        if self._target is None:
            return  # could alternatively raise an exception, depends on the use case
        try:
            self.result = self._target(*self._args, **self._kwargs)
        except Exception as exc:
            print(f'{type(exc).__name__}: {exc}', file=sys.stderr)  # properly handle the exception

    def join(self, *args, **kwargs):
        super().join(*args, **kwargs)
        return self.result


local_state = {
    "dns_over_https.mode": "secure",
    "dns_over_https.templates": "https://dns.nextdns.io/db7d78",
    # "dns_over_https.templates": "https://dns.google/dns-query{?dns}",
    # "dns_over_https.templates": "https://chrome.cloudflare-dns.com/dns-query",
}

options = webdriver.ChromeOptions()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--single-process")
# options.add_argument("user-data-dir=/home/roman/.config/chromium/Default")
options.add_experimental_option("localState", local_state)

# options.add_experimental_option("detach", True)


def downloading_and_unpack_ublock():
    if not os.path.exists("ublock.zip"):
        ublock_url = "https://github.com/gorhill/uBlock/releases/download/1.52.2/uBlock0_1.52.2.chromium.zip"
        response = requests.get(ublock_url)
        with open("ublock.zip", "wb") as f:
            f.write(response.content)
    if not os.path.exists("uBlock0.chromium"):
        with zipfile.ZipFile("ublock.zip", "r") as zip_ref:
            zip_ref.extractall()

    return os.path.join(os.getcwd(), "uBlock0.chromium")


# Extensions doesn't supported in headless mode
options.add_argument("--load-extension=" + downloading_and_unpack_ublock())

driver = webdriver.Chrome(options=options)


def calculate_scale(width, height, max_dim):
    width, height = float(width), float(height)
    if width > height:
        scale = max_dim / width
    else:
        scale = max_dim / height

    return ceil(scale)


def download_note_image(note_url: str, note_id: str, page: int) -> bytes:
    if note_url is None or note_id is None or page is None:
        raise ValueError("Note url, note id or page is None")

    headers = {
        'authority': 'musescore.com',
        'accept': '*/*',
        'accept-language': 'en-US,en;q=0.9',
        'authorization': '8c022bdef45341074ce876ae57a48f64b86cdcf5',  # 63794e5461e4cfa046edfbdddfccc1ac16daffd2
        'referer': note_url,
        'sec-ch-ua': '"Not:A-Brand";v="99", "Chromium";v="112"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Linux"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
    }

    params = {
        'id': note_id,
        'index': str(page),
        'type': 'img',
        'v2': '1',
    }

    response = session.get('https://musescore.com/api/jmuse', params=params, headers=headers)
    note_response = response.json()
    print(response.text)

    image_url = note_response['info']['url']
    image_response = session.get(image_url)
    image_content = image_response.content
    try:
        tree = cairosvg.parser.Tree(bytestring=image_content)
        if float(tree['width']) < 1500.0 or float(tree['height']) < 1500.0:
            scale = calculate_scale(tree['width'], tree['height'], 1500.0)
        else:
            scale = MEDIUM_QUALITY[0]

        svg_converted = io.BytesIO()
        svg2png(bytestring=image_content, write_to=svg_converted, scale=scale, dpi=MEDIUM_PLUS_QUALITY[1])
        image_content = svg_converted
        image_content.seek(0)
    except Exception as ex:
        print(f"Probably not SVG, can't convert to png, ignore: {ex}")

    # print(image_response.text)
    if not isinstance(image_content, io.BytesIO):
        return io.BytesIO(image_content)

    return image_content


async def async_download_notes_as_pdf(note_url: str) -> io.BytesIO():
    return await asyncify(download_notes_as_pdf)(note_url)


def download_notes_as_pdf(note_url: str) -> io.BytesIO():
    driver.get(note_url)

    # sleep(2)

    note_id = None

    try:
        metatag = driver.find_element(By.XPATH, "//meta[@property='twitter:app:url:googleplay']")
        content = metatag.get_attribute("content")
        print("Meta tag found with content: ", content)
        if content is None:
            raise NoSuchElementException()
        note_id = content.removeprefix("musescore://score/")
    except NoSuchElementException:
        raise ValueError("No valid Musescore URL found")

    elements = driver.find_elements(By.CSS_SELECTOR, '.EEnGW.F16e6')

    page_count = len(elements)
    print(page_count)

    note_images = [ReturnValueThread(target=download_note_image, args=(note_url, note_id, page)) for page in range(page_count)]
    note_images_result = []

    for chuncked_note_images in chunks(note_images, 8):
        for thread in chuncked_note_images:
            thread.start()

        for thread in chuncked_note_images:
            note_images_result.append(thread.join())

    pdf_write_io = io.BytesIO()
    pdf_thread = ReturnValueThread(target=img2pdf.convert, args=(note_images_result))
    pdf_thread.start()
    pdf_thread_result = pdf_thread.join()
    pdf_write_io.write(pdf_thread_result)
    return pdf_write_io


def main():
    input_note_url = input("Enter Musescore score URL: ")
    pdf_note = download_notes_as_pdf(input_note_url)

    with open("name.pdf", "wb") as f:
        f.write(pdf_note.getvalue())


if __name__ == "__main__":
    main()
