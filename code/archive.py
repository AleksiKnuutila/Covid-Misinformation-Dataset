from common import logger
from common import config

import os
import sys
import re

import pandas as pd
import numpy as np
import seaborn as sns
from tqdm import tqdm
import csv

import aiohttp
import asyncio
import requests
from lxml import html

from tenacity import retry, retry_if_exception_type, stop_after_attempt, RetryError
from asyncio import TimeoutError

from IPython.core import ultratb

sys.excepthook = ultratb.FormattedTB(mode="Verbose", color_scheme="Linux", call_pdb=1)


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
    "title": (
        "//script[re:test(text(),'\\\?\\\?\"title\\\?\\\?\":', '')]//text()",
        '\\\?\\\?"title\\\\?\\\\?":\\\\?\\\\?"([^"]+")',
    ),
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
targets_youtube_removed_run2 = {
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

targets_archive = {
    "viewcount": ("//div[@class='watch-view-count']", ""),
    "title": ("//span[@id='eow-title']", ""),
    "channel": ("//div[@class='yt-user-info']", ""),
    "subscribers": ("subscribers", "([0-9KM]+ subscribers)"),
}


class ScraperError(Exception):
    pass


class InvalidUrl(Exception):
    pass


async def get_archive_urls(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(
            "http://web.archive.org/web/timemap/link/" + url
        ) as response:
            resp = await response.text()
            lines = resp.splitlines()
            logger.debug("Found %s archive links for %s" % (len(lines[3:]), url))
            return [
                str(line)
                .split(";")[0]
                .replace("<", "")
                .replace(">", "")
                .replace("b'", "")
                for line in reversed(lines[3:])
            ]


def scrape_date(archive_url):
    if not "archive.org" in archive_url:
        return ""
    return re.search("archive.org\/web\/([0-9]{14})", archive_url).group(1)


async def get_yt_data(youtube_url, archive_urls):
    logger.debug("Getting YT data for %s, %s links" % (youtube_url, len(archive_urls)))
    first_removed_url = ""
    main_data_point = ""
    all_data_points = []
    for archive_url in archive_urls:
        logger.debug("Trying for link related to %s, %s" % (youtube_url, archive_url))
        try:
            data = {}
            data = await scrape(archive_url)
            data["archiveUrl"] = data["url"]
            data["url"] = youtube_url
            # Found video metadata -> not deleted at this stage
            data["scrapedAt"] = scrape_date(archive_url)
            if data["title"] and not main_data_point:
                data["removalAt"] = scrape_date(first_removed_url)
                # break
                main_data_point = data
            # Found removal notification
            elif data["status"] and not 'status":"OK"' in data["status"]:
                logger.debug(
                    "Found removal notice for %s at %s" % (youtube_url, archive_url)
                )
                first_removed_url = archive_url
            all_data_points.append(data)
        except ScraperError:
            logger.debug(
                "Got ScraperError related to %s, for URL %s"
                % (youtube_url, archive_url)
            )
            continue
        except InvalidUrl:
            logger.warning("InvalidUrl for %s, %s" % (youtube_url, archive_url))
            continue
        except UnicodeDecodeError:
            logger.warning("UnicodeDecodeError for %s, %s" % (youtube_url, archive_url))
            continue
        except (aiohttp.ServerTimeoutError, asyncio.TimeoutError):
            logger.warning("TimeoutError for %s, %s" % (youtube_url, archive_url))
            continue
    if not data or (data["status"] and not data["title"]):
        logger.warning("Could not find data for %s" % youtube_url)
    else:
        if main_data_point:
            data = main_data_point
        return {**data, **{"all_archived_data_points": all_data_points}}


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
            if title == "subscriberCount":
                data = [""]
            else:
                raise ScraperError(
                    "URL doesn't contain required data on key '%s'" % title
                )
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


# unused
async def get_and_extract(url):
    try:
        return await scrape(url)
    except ScraperError:
        logger.warning("Unhandled ScraperError for %s" % url)
        return None
    except InvalidUrl:
        logger.warning("InvalidUrl for %s" % url)
        return None
    except (
        concurrent.futures._base.TimeoutError,
        aiohttp.ServerTimeoutError,
        aiohttp.TimeoutError,
        asyncio.TimeoutError,
    ):
        logger.warning("TimeoutError for %s" % url)
        return None
    except UnicodeDecodeError:
        logger.warning("UnicodeDecodeError for %s" % url)
        return None


async def scrape(url):
    async with aiohttp.ClientSession(read_timeout=30) as session:
        async with session.get(url) as response:
            if response.status == 404:
                raise InvalidUrl
            data = extract_targets_from_page(
                await response.text(),
                [
                    targets_youtube,
                    targets_youtube_run2,
                    targets_youtube_removed,
                    targets_youtube_removed_run2,
                ],
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


sourcefn = sys.argv[1]
targetfn = sys.argv[2]

df = pd.read_csv(sourcefn)
urls = list(df["url"].unique())
fields = (
    ["url"]
    + list(targets_youtube.keys())
    + ["scrapedAt", "removalAt", "archiveUrl", "all_archived_data_points"]
)

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

BATCHSIZE = 8
loop = asyncio.get_event_loop()

with open(targetfn, "a") as f:
    writer = csv.writer(f)
    for url_range in tqdm(reversed(range(0, len(urls), BATCHSIZE))):
        url_batch = urls[url_range : url_range + BATCHSIZE]
        url_batch = [
            url for url in url_batch if url not in read_urls and valid_url(url)
        ]
        if not url_batch:
            continue
        coroutines = [get_archive_urls(url) for url in url_batch]
        results = loop.run_until_complete(asyncio.gather(*coroutines))

        coroutines = [
            get_yt_data(yt_url, archive_urls)
            for yt_url, archive_urls in zip(url_batch, results)
            if archive_urls
        ]
        results = loop.run_until_complete(asyncio.gather(*coroutines))

        for data in [res for res in results if res]:
            writer.writerow([data[x] for x in fields])