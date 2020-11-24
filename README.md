# A dataset of Covid-related misinformation videos and their spread on social media

# Authors

Aleksi Knuutila, Aliaksandr Herasimenko, Jonathan Bright, Philip N. Howard

Affiliation: Oxford Internet Institute, Computational Propaganda Project

# Abstract

This dataset contains metadata about all Covid-related YouTube videos which circulated on public social media, but which YouTube eventually removed because they contained false information. It describes 8,122 videos that were shared between November 2019 and June 2020. The dataset contains unique identifiers for the videos and social media accounts that shared the videos, statistics on social media engagement and metadata such as video titles and view counts where they were recoverable. We publish the data alongside the code used to produce on Github. The dataset has reuse potential for research studying narratives related to the coronavirus, the impact of social media on knowledge about health and the politics of social media platforms.

# Keywords

Coronavirus, misinformation, social media, content moderation, platform policies

# Context

Misinformation and conspiratorial claims related to the coronavirus are a problem for stemming the pandemic. Studies have shown that believing in conspiracy theories makes people less likely to participate in behaviors that protect their health, such as obtaining vaccinations.[@dunnMappingInformationExposure2017] While all large social media platforms can host misinformation, research suggests that YouTube has played a particularly important role as a source for misinformation related to the Coronavirus pandemic.[@allingtonHealthprotectiveBehaviourSocialundefined/ed]

In April 2020, YouTube’s Chief Executive Susan Wojcicki stated that the company was increasing its efforts to remove “medically unsubstantiated” videos. YouTube publishes only aggregated information about the videos that break its Community Guidelines and that are removed. It is, however, possible to gather information about individual removed videos from various public data sources. These data sources have their limitations, but the resulting dataset is a relatively comprehensive sample of videos that circulated on social media and then were removed by YouTube because they contained false information.

The data was created for the Computational Propaganda Project at the Oxford Internet Institute, in order to study the scale of the audience of Covid-related misinformation and its mechanisms of distribution on social media.

# Methods

## Steps

This dataset describes 8,122 YouTube videos that contain Covid-related misinformation. We identify these videos by following the categorisations made by YouTube itself.

We identified Covid-related videos by looking for posts on Facebook, Reddit and Twitter that link to YouTube and that match Covid-related keywords. For Twitter, we used an open access dataset that that covered the period from October, 2019 to the end of April, 2020.[@dimitrovTweetsCOV19KnowledgeBase2020] This dataset was based on a set 268 Covid-related keywords. We simplified and updated this list of keywords to a total of 71 keywords [@knuutilaCovidrelatedMisinformationYouTube]. We used the CrowdTangle service to search for posts on Reddit and Facebook between the 1st of October 2019 and the 30th of June 2020. CrowdTangle is a database that contains public groups and pages from Facebook and Reddit.[@WhatDataCrowdTangle]

This search resulted in a list of 1,091,876 distinct videos. We then followed the YouTube link to each video, and where the videos were no longer available we recorded the reason that the YouTube site gave for the video having been removed. With this method, we identified 8,122 Covid-related videos that YouTube had removed because they breached is Community Guidelines.

For these 8,122 videos, we recovered additional information and metadata from other sources, since YouTube itself only published the reason for their removal. Firstly, we recovered the titles and part of the description for all the videos that have been posted to Facebook. The posts on Facebook displayed the original titles and the first 157 characters of the video's description, which we could read by programmatically retrieving every Facebook post. We also queried the Facebook Graph API to get the total number of shares, comments and reactions that the videos had received across the entire platform, including posts to individual profiles and closed groups. The data collection was undertaken in July, 2020.

Lastly, we recovered metadata about the videos from the archive.org’s “WayBack Machine”, a service that archives the older versions of webpages. Copies of the deleted YouTube pages were accessible through the WayBack Machine's API in 935 cases. For these videos, we could access the view counts, channel subscriber counts, full descriptions of the videos as well as the video's creation date. In 420 cases, we were also able to approximate how long the video had been visible, by noting the date at which the WayBack Machine had archived the first copy of video's page that stated its removal.

## Quality control

We are publishing the ID numbers of Tweets and Facebook posts instead of publishing the contents of those posts. This is in accordance with the policies of Facebook and Twitter, and to ensure that no personally identifiable information is made public. Researchers can access additional data about the posts by querying the APIs provided by the platforms based on the ID numbers in the dataset.

# Dataset and code

The dataset is located in the dataset folder and the python code to create it is in the code folder.

## License

CC-BY