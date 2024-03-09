import io
import os
import zipfile
from math import ceil
from time import sleep
from urllib.parse import urlencode, urljoin

import cairosvg
import img2pdf
import requests
from asyncer import asyncify
from cairosvg import svg2png
from loguru import logger
from pyvirtualdisplay import Display
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.firefox_profile import FirefoxProfile
from selenium.webdriver import ChromeOptions
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from seleniumrequests import Chrome, Firefox

from utils import ReturnValueThread, chunks

MEDIUM_QUALITY = (1.5, 200)
MEDIUM_PLUS_QUALITY = (2, 300)

display = Display(visible=0, size=(800, 600))
# display.start()


local_state = {
    "dns_over_https.mode": "secure",
    "dns_over_https.templates": "https://dns.nextdns.io/db7d78",
    # "dns_over_https.templates": "https://dns.google/dns-query{?dns}",
    # "dns_over_https.templates": "https://chrome.cloudflare-dns.com/dns-query",
}

chrome_options = ChromeOptions()
# chrome_options.add_argument("--headless")
# chrome_options.add_argument("--window-size=1920x1080")
# chrome_options.add_argument("--no-sandbox")
# chrome_options.add_argument("--single-process")
# chrome_options.add_argument("user-data-dir=/home/roman/.config/chromium/Default")
chrome_options.add_experimental_option("localState", local_state)

firefox_path = "/usr/bin/firefox-aurora"
firefox_options = FirefoxOptions()
firefox_options.binary_location = firefox_path
# firefox_options.add_argument("--headless")  # Uncomment if headless mode is desired
firefox_options.add_argument("--width=1920")
firefox_options.add_argument("--height=1080")
# Firefox does not have a direct equivalent for "--no-sandbox" or "--single-process"
# These are specific to Chrome and Chromium-based browsers.

firefox_profile = FirefoxProfile("/tmp/firefox_profile")

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
chrome_options.add_argument("--load-extension=" + downloading_and_unpack_ublock())

driver = Chrome(options=chrome_options)
# driver = Firefox(firefox_profile, options=firefox_options)


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
        'Authorization': '33b3',  # 63794e5461e4cfa046edfbdddfccc1ac16daffd2
        'Referer': note_url,
        'Cookie': 'mu_browser_bi=1974794642206237275; mu_browser_uni=ceo_mbj3; _mu_unified_id=1.1706516430.373992574; mu_ab_experiment=3682.3_4183.2_4240.1_4360.1_4393.2_4414.2_4417.1_4435.1_4441.2_4447.2_4450.2_4456.2_4471.2_4477.2_4489.2_4498.3_4501.1_4519.2_4525.1_4528.2; _mu_session_id=1.1710010160.1710010523; learn.tooltip.view.count=2; mscom_new=b20afb10f70c9963f3b5d1285284b8ed; _mu_dc_regular=%7B%22v%22%3A2%2C%22t%22%3A1710007253%7D; _mu_user_segmentation=segment.5_pred.0_group.2_events.8_loads.0_rec.7_freq.2; _csrf=2PrtalwqZAVyyfNFA6SanQL3eI8SsNwp; mu_has_static_cache=1710007253; _ms_adScoreView=6; __cf_bm=H07YDrZllWqCzll1XXn0lV3e.nnEHyXhoUICe6oXyaI-1710010161-1.0.1.1-NZkoUlInzCSs5H8fukQ9bIhay_DQGdMj_DhkYIKLNNtE2uWpl2oSC5kRXJdY4CQatdEHfgKcuHSr8GhyoFGUIQ; _ga=GA1.2.2129050638.1710010162; _gid=GA1.2.1700830849.1710010162'
    }

    params = {
        'id': note_id,
        'index': str(page),
        'type': 'img',
    }

    get_url = urljoin("https://musescore.com/api/jmuse", "?" + urlencode(params))
    logger.debug(f"{get_url=}")

    response = driver.request('GET', get_url, headers=headers)
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
