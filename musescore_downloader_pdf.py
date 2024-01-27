# pip install cairosvg img2pdf pyTelegramBotAPI asyncer sentry-sdk selenium selenium-requests loguru
import io
import os
import sys
import io
import threading
import zipfile
from math import ceil

import cairosvg
import img2pdf
from loguru import logger
from time import sleep
import requests
from asyncer import asyncify
from cairosvg import svg2png
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By

from urllib.parse import urlencode, urljoin

from seleniumrequests import Chrome

from pyvirtualdisplay import Display

MEDIUM_QUALITY = (1.5, 200)
MEDIUM_PLUS_QUALITY = (2, 300)

display = Display(visible=0, size=(800, 600))
display.start()

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
# options.add_argument("--headless")
# options.add_argument("--window-size=1920x1080")
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

driver = Chrome(options=options)


def calculate_scale(width, height, max_dim):
    width, height = float(width), float(height)
    if width > height:
        scale = max_dim / width
    else:
        scale = max_dim / height

    return ceil(scale)


def download_note_image(note_url: str, note_id: str, page: int) -> bytes:
    if note_url is None or note_id is None or page is None:
        logger.debug(f"Raising error, since not valid values was gathered: {note_url=}, {note_id=}, {page=}")
        raise ValueError("Note url, note id or page is None")

    headers = {
        'authorization': '8c022bdef45341074ce876ae57a48f64b86cdcf5',  # 63794e5461e4cfa046edfbdddfccc1ac16daffd2
        'referer': note_url
    }

    params = {
        'id': note_id,
        'index': str(page),
        'type': 'img',
        'v2': '1',
    }

    get_url = urljoin("https://musescore.com/api/jmuse", "?" + urlencode(params))

    response = driver.request('GET', get_url, headers=headers)
    logger.debug(response)
    logger.debug(f"Response status code: {response.status_code}. Response: {response.text}")
    note_response = response.json()
    logger.debug(note_response)

    image_url = note_response['info']['url']
    logger.debug(f"Downloading image: {image_url}")
    image_response = driver.request('GET', image_url)

    image_content = image_response.content
    logger.debug(image_content)
    
    try:
        tree = cairosvg.parser.Tree(bytestring=image_content)
        if float(tree['width']) < 1500.0 or float(tree['height']) < 1500.0:
            scale = calculate_scale(tree['width'], tree['height'], 1500.0)
        else:
            scale = MEDIUM_QUALITY[0]

        svg_converted = io.BytesIO()
        svg2png(bytestring=image_content, write_to=svg_converted, scale=scale, dpi=MEDIUM_QUALITY[1])
        image_content = svg_converted
        image_content.seek(0)
    except Exception as ex:
        print(f"Probably not SVG, can't convert to png, ignore: {ex}")

    if not isinstance(image_content, io.BytesIO):
        return io.BytesIO(image_content)

    return image_content


async def async_download_notes_as_pdf(note_url: str) -> io.BytesIO():
    return await asyncify(download_notes_as_pdf)(note_url)


def download_notes_as_pdf(note_url: str) -> io.BytesIO():
    driver.get(note_url)

    sleep(2)

    note_id = None

    """
    i = 0
    while True:
        png = driver.get_screenshot_as_png()
        arr = np.frombuffer(png, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        cv2.imshow('Webpage Screenshot', img)
        cv2.waitKey(1 * 5_000)
        cv2.destroyAllWindows()
        sleep(1)
        i += 1
    """

    try:
        WebDriverWait(driver, 100).until(lambda driver: driver.execute_script('return document.readyState') == 'complete')
        metatag = driver.find_element(By.XPATH, "//meta[@property='al:android:url']")
        content = metatag.get_attribute("content")
        logger.debug(f"Meta tag found with content: {content}")
        if content is None:
            raise NoSuchElementException()
        note_id = content.removeprefix("musescore://score/")
        logger.debug(f"{note_id=}")
    except NoSuchElementException:
        raise ValueError("No valid Musescore URL found")

    elements = driver.find_elements(By.CSS_SELECTOR, '.EEnGW.F16e6')

    page_count = len(elements)
    logger.debug(f"{page_count=}")

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

    driver.quit()
    display.stop()
