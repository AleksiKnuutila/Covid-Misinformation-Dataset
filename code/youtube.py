from common import logger
from common import config

import aiohttp
import asyncio
import requests
from lxml import html
import pandas as pd
import numpy as np
import seaborn as sns
from tqdm import tqdm
import csv

from tenacity import retry, retry_if_exception_type, stop_after_attempt, RetryError
from IPython.core import ultratb

import os
import sys
import re

sys.excepthook = ultratb.FormattedTB(mode="Verbose", color_scheme="Linux", call_pdb=1)

sourcefn = sys.argv[1]
targetfn = sys.argv[2]

# Data to be extracted, tuple of XPath and a regexp, applied consecutively
targets_youtube = {
    "status": (),
    "title": ("//meta[@name='title']/@content", ""),
    "description": (
        "//p[@id='eow-description']//text()",
        "",
    ),
    "publishedAt": (
        "//strong[@class='watch-time-text']//text()",
        "",
    ),
    "viewCount": ("//div[@class='watch-view-count']//text()", ""),
    "channelId": ("//meta[@itemprop='channelId']/@content", ""),
    "duration": ("//meta[@itemprop='duration']/@content", ""),
    "channelUrl": ("//link[@itemprop='url']/@href", ""),
    "subscriberCount": (
        "//span[@class='yt-subscription-button-subscriber-count-branded-horizontal yt-subscriber-count']//text()",
        "",
    ),
}

targets_youtube_run2 = {
    "status": (),
    "title": ("//meta[@name='title']/@content", ""),
    "description": (
        "//script[re:test(text(),'description\\\?\":', '')]//text()",
        'description\\\?\\\?":({[^}]+})',
    ),
    "publishedAt": (
        "//script[re:test(text(),'dateText\\\?\":', '')]//text()",
        'dateText\\\?\\\?":({[^}]+})',
    ),
    "viewCount": (
        "//script[re:test(text(),'viewCount\\\?\":', '')]//text()",
        'viewCount\\\\?\\\\?":\\\\?\\\\?"([^"]+")',
    ),
    "channelId": (
        "//script[re:test(text(),'channelId\\\?\":', '')]//text()",
        'channelId\\\\?\\\\?":\\\\?\\\\?"([^"]+")',
    ),
    "duration": (),
    "channelUrl": (),
    "subscriberCount": (
        "//script[re:test(text(),'subscriberCountText\\\?\":', '')]//text()",
        'subscriberCountText\\\?\\\?":({[^}]+})',
    ),
}

# Data to be extracted from removed videos
targets_youtube_removed = {
    "status": ("//h1[@id='unavailable-message']//text()", ""),
    "video_url": (),
    "title": (),
    "description": (),
    "publishedAt": (),
    "viewCount": (),
    "channelId": (),
    "duration": (),
    "channelUrl": (),
    "subscriberCount": (),
}
targets_youtube_removed = {
    "status": (
        "//script[contains(text(),'playabilityStatus\":')]//text()",
        'playabilityStatus":({[^}]+})',
    ),
    "video_url": (),
    "title": (),
    "description": (),
    "publishedAt": (),
    "viewCount": (),
    "channelId": (),
    "duration": (),
    "channelUrl": (),
    "subscriberCount": (),
}


class ScraperError(Exception):
    pass


class InvalidUrl(Exception):
    pass


def valid_url(url):
    if url == "https://youtube.com/watch?v=":
        return False
    if len(url) != 39:
        return False
    if "youtube.com/watch" in url or "youtu.be" in url:
        return True
    return False


def apply_xpath_and_regexp(tree, target):
    results = {}
    for title, target in target.items():
        if not target:
            results[title] = ""
            continue
        xpath, regexp = target
        data = tree.xpath(
            xpath, namespaces={"re": "http://exslt.org/regular-expressions"}
        )
        if not data:
            raise ScraperError("URL doesn't contain required data on key '%s'" % title)
        data = data[0]
        if regexp and data:
            match = re.search(regexp, data)
            if not match:
                raise ScraperError(
                    "URL doesn't contain matching regexp for key '%s'" % title
                )
            data = match.group(0)
        results[title] = data
    return results


async def async_scrape(url):
    try:
        return await scrape(url)
    except ScraperError:
        logger.warning("Unhandled ScraperError for %s" % url)
        return None
    except InvalidUrl:
        logger.warning("InvalidUrl for %s" % url)
        return None


@retry(
    stop=stop_after_attempt(5),
    retry=retry_if_exception_type(
        (
            aiohttp.client_exceptions.ClientConnectorError,
            aiohttp.ServerDisconnectedError,
            aiohttp.ClientOSError,
        )
    ),
)
async def scrape(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 404:
                raise InvalidUrl
            try:
                data = extract_targets_from_page(
                    await response.text(), [targets_youtube, targets_youtube_run2]
                )
            except (ScraperError, RetryError):
                data = extract_targets_from_page(
                    await response.text(),
                    [targets_youtube_removed, targets_youtube_removed2],
                )
            return {**data, **{"url": url}}


@retry(stop=stop_after_attempt(2), retry=retry_if_exception_type(ScraperError))
def extract_targets_from_page(pagecontent, targets):
    tree = html.fromstring(pagecontent)
    if isinstance(targets, dict):
        targets = [targets]

    for idx, target in enumerate(targets):
        try:
            data = apply_xpath_and_regexp(tree, target)
            break
        except ScraperError as e:
            if idx + 1 == len(targets):
                raise ScraperError(e)
            else:
                continue
    return data


def get_yt_link(x):
    try:
        m = re.search("(v\=|youtu.be/)([a-zA-Z0-9_\-]+)", x)
    except TypeError:
        return ""
    if not m:
        return x
    return "https://youtube.com/watch?v=" + m.groups()[1]


def get_yt_id(x):
    try:
        m = re.search("(v\=|youtu.be/)([a-zA-Z0-9_\-]+)", x)
    except TypeError:
        return ""
    if not m:
        return ""
    return m.groups()[1]


df = pd.read_csv(sourcefn)
df["yt_id"] = df["link"].apply(get_yt_id)
df["yt_link"] = "https://youtube.com/watch?v=" + df["yt_id"]

urls = list(df["yt_link"].unique())
fields = ["url"] + list(targets_youtube.keys())

if os.path.isfile(targetfn):
    try:
        current_data = pd.read_csv(targetfn)
        read_urls = current_data["url"].values
    except pd.errors.EmptyDataError:
        read_urls = []
else:
    read_urls = []
    # headers
    with open(targetfn, "w") as f:
        writer = csv.writer(f)
        writer.writerow(fields)

BATCHSIZE = 32
loop = asyncio.get_event_loop()

urls = list(set(urls) - set(read_urls))

with open(targetfn, "a") as f:
    writer = csv.writer(f)
    for url_range in tqdm(range(0, len(urls), BATCHSIZE)):
        url_batch = urls[url_range : url_range + BATCHSIZE]
        url_batch = [url for url in url_batch if url and valid_url(url)]
        if url_batch:
            coroutines = [async_scrape(url) for url in url_batch]
            results = loop.run_until_complete(asyncio.gather(*coroutines))
            for data in [res for res in results if res]:
                writer.writerow([data[x] for x in fields])