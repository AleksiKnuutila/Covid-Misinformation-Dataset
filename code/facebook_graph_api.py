import sys
import os

import pandas as pd
import numpy as np
from tqdm import tqdm
import csv

from graphclient import GraphClient
from common import config

sourcefn = sys.argv[1]
targetfn = sys.argv[2]

links = pd.read_csv(sourcefn)

urls = list(links["url"].values)

client = GraphClient(config["graph-tokens"])

current_data = pd.read_csv(targetfn)
read_urls = current_data["yt_link"].values

with open(targetfn, "a") as f:
    writer = csv.writer(f)
    fields = [
        "url",
        "reaction_count",
        "comment_count",
        "share_count",
        "comment_plugin_count",
    ]
    for url in tqdm(urls):
        if url in read_urls:
            continue
        data = client.get_engagement(url)
        if data is not None:
            writer.writerow([data[x] for x in fields])
