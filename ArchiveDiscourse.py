#!/usr/bin/env python
"""
Archive a Discourse site.
"""

import os
import sys
import base64
from datetime import date
from shutil import rmtree, copyfile
import argparse
from urllib.parse import urlparse
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup as bs
from PIL import Image
from io import BytesIO
from time import sleep

parser = argparse.ArgumentParser(description="Archive a Discourse site.")
parser.add_argument("base_url", type=str, help="Base URL of website")
parser.add_argument(
    "path",
    type=str,
    nargs="?",
    default=os.getcwd(),
    help="Where to save (defaults to current directory)",
)
parser.add_argument(
    "--max-retries",
    type=int,
    default=5,
    help="Number of times to retry fetching each file",
)
parser.add_argument(
    "--wait", type=int, default=1, help="Number of seconds to wait between web requests"
)
parser.add_argument(
    "--max-more-topics",
    type=int,
    default=100,
    help="Max number of pages to get from the topic list",
)
parser.add_argument(
    "--force", action="store_true", help="Overwrite target directory if it exists"
)
args = parser.parse_args()

base_url = args.base_url.rstrip("/")
domain = urlparse(base_url).netloc
script_path = os.path.dirname(os.path.abspath(__file__))
target_path = os.path.join(args.path, domain)
today = date.today()
archive_blurb = f"A partial archive of {base_url} as of {today:%A %B %d, %Y}."

# Note that the directory specified by `path` will be overwritten.

# When archiving larger sites (like meta.discourse.org), you might need to
# increase the number of retries to connect.
# Doesn't seem to be necessary for my site but it *is* necessary for Meta.

s = requests.Session()
s.mount(base_url, HTTPAdapter(max_retries=args.max_retries))

# Templates for the webpages
base_scheme = urlparse(base_url).scheme

# Template for the main page. Subsequent code will replace a few items indicated by
# <!-- COMMENTS -->
with open("templates/main.html", "r") as f:
    main_template = f.read()

# Template for the individual topic pages
with open("templates/topic.html", "r") as f:
    topic_template = f.read()

# Function that writes out each individual topic page
def write_topic(topic_json):
    topic_download_url = (
        base_url + "/t/" + topic_json["slug"] + "/" + str(topic_json["id"])
    )
    topic_relative_url = "t/" + topic_json["slug"] + "/" + str(topic_json["id"])
    try:
        os.makedirs(topic_relative_url)
    except Exception as err:
        print("in write_topic error:", "make directory")
    response = requests.get(topic_download_url + ".json")
    posts_json = response.json()["post_stream"]["posts"]
    post_list_string = ""
    for post_json in posts_json:
        post_list_string = post_list_string + post_row(post_json)
    topic_file_string = (
        topic_template.replace("<!-- TOPIC_TITLE -->", topic_json["fancy_title"])
        .replace("<!-- JUST_SITE_TITLE -->", str(site_title.text))
        .replace("<!-- ARCHIVE_BLURB -->", archive_blurb)
        .replace("<!-- POST_LIST -->", post_list_string)
    )

    f = open(topic_relative_url + "/index.html", "w")
    f.write(topic_file_string)
    f.close()


# Function that creates the text describing the individual posts in a topic
def post_row(post_json):
    avatar_url = post_json["avatar_template"]
    parsed_url = urlparse(avatar_url)
    path = parsed_url.path
    avatar_file_name = path.split("/")[-1]
    if parsed_url.netloc and parsed_url.scheme:
        pass
    elif parsed_url.netloc:
        avatar_url = base_scheme + ":" + avatar_url
    else:
        avatar_url = base_url + avatar_url
    #    if(not parsed_url.scheme):
    #        if avatar_url[0] == '/':
    #            avatar_url = base_url + avatar_url
    #        else:
    #            avatar_url = base_scheme + '://' + avatar_url
    avatar_url = avatar_url.replace("{size}", "45")
    if not os.path.exists(os.getcwd() + "/images/" + avatar_file_name):
        try:
            response = requests.get(avatar_url, stream=True)
            img = Image.open(BytesIO(response.content))
            img.save(os.getcwd() + "/images/" + avatar_file_name)
        except Exception as err:
            template = "An exception of type {0} occured. Arguments:\n{1!r}"
            message = template.format(type(err).__name__, err.args)
            print(
                "in post_row error:",
                "write avatar",
                avatar_url,
                message,
                cnt,
                topic["slug"],
                "\n===========\n",
            )
            # sys.exit(0)

    user_name = post_json["username"]
    content = post_json["cooked"]

    # Since we don't generate user information,
    # replace any anchors of class mention with a span
    soup = bs(content, "html.parser")
    mention_tags = soup.findAll("a", {"class": "mention"})
    for tag in mention_tags:
        try:
            rep = bs('<span class="mention"></span>', "html.parser").find("span")
            rep.string = tag.string
            tag.replaceWith(rep)
        except TypeError:
            pass

    img_tags = soup.findAll("img")
    for img_tag in img_tags:
        img_url = img_tag["src"]
        parsed_url = urlparse(img_url)
        path = parsed_url.path
        file_name = path.split("/")[-1]
        if parsed_url.netloc and parsed_url.scheme:
            pass
        elif parsed_url.netloc:
            img_url = base_scheme + ":" + img_url
        else:
            img_url = base_url + img_url
        # response = requests.get('http:' + img_url, stream=True)
        try:
            response = requests.get(img_url, stream=True)
            img = Image.open(BytesIO(response.content))
            img.save(os.getcwd() + "/images/" + file_name)
            img_tag["src"] = "../../../images/" + file_name
            # print('good', file_name, img_url)
        except Exception as err:
            template = "An exception of type {0} occured. Arguments:\n{1!r}"
            message = template.format(type(err).__name__, err.args)
            print("post_row", "save image", file_name, img_url, message)
            img_tag["src"] = "../../../images/missing_image.png"
            # sys.exit(0)

    content = ""
    for s in soup.contents:
        content = content + str(s)

    post_string = '      <div class="post_container">\n'
    post_string = post_string + '        <div class="avatar_container">\n'
    post_string = (
        post_string
        + '          <img src="../../../images/'
        + avatar_file_name
        + '" class="avatar" />\n'
    )
    post_string = post_string + "        </div>\n"
    post_string = post_string + '        <div class="post">\n'
    post_string = (
        post_string + '          <div class="user_name">' + user_name + "</div>\n"
    )
    post_string = post_string + '          <div class="post_content">\n'
    post_string = post_string + content + "\n"
    post_string = post_string + "          </div>\n"
    post_string = post_string + "        </div>\n"
    post_string = post_string + "      </div>\n\n"
    return post_string


# The topic_row function generates the HTML for each topic on the main page
category_url = base_url + "/categories.json"
response = requests.get(category_url)
category_json = response.json()["category_list"]["categories"]
category_id_to_name = dict([(cat["id"], cat["name"]) for cat in category_json])


def topic_row(topic_json):
    topic_html = '      <div class="topic-row">\n'
    topic_url = "t/" + topic_json["slug"] + "/" + str(topic_json["id"])
    topic_title_text = topic_json["fancy_title"]
    topic_post_count = topic_json["posts_count"]
    topic_pinned = topic_json["pinned_globally"]
    try:
        topic_category = category_id_to_name[topic_json["category_id"]]
    except KeyError:
        topic_category = ""

    topic_html = topic_html + '        <span class="topic">'
    if topic_pinned:
        topic_html = topic_html + '<i class="fa fa-thumb-tack"'
        topic_html = topic_html + ' title="This was a pinned topic so it '
        topic_html = topic_html + 'appears near the top of the page."></i>'
    topic_html = topic_html + '<a href="' + topic_url + '">'
    topic_html = topic_html + topic_title_text + "</a></span>\n"
    topic_html = topic_html + '        <span class="category">'
    topic_html = topic_html + topic_category + "</span>\n"
    topic_html = topic_html + '        <span class="post-count">'
    topic_html = topic_html + str(topic_post_count) + "</span>\n"
    topic_html = topic_html + "      </div>\n\n"
    return topic_html


# The action is just starting here.

# Check for the directory where plan to store things.
# Note that this will be overwritten!
if os.path.exists(target_path):
    if not os.path.isdir(target_path):
        sys.exit(f"{target_path} exists and is not a directory")
    elif args.force:
        rmtree(target_path)
    else:
        sys.exit(f"{target_path} exists (use --force to overwrite")

os.mkdir(target_path)
os.chdir(target_path)
os.mkdir("images")

# Grab the site title and logo - available via the API but only after login
# so we'll grab this one thing via Beautiful Soup.
response = requests.get(base_url)
soup = bs(response.content, "html.parser")
site_title = soup.title
site_logo = soup.find("img", {"id": "site-logo"})
if site_logo == None:
    copyfile(
        script_path + "/files/site-logo.png", os.getcwd() + "/images/site-logo.png"
    )
else:
    # site_logo_image_url = base_url + site_logo.attrs['src']
    ## Looks like maybe the API changed?
    site_logo_image_url = site_logo.attrs["src"]
    parsed = urlparse(site_logo_image_url)
    if parsed.netloc == "":
        site_logo_image_url = base_url + site_logo_image_url
    response = requests.get(site_logo_image_url, stream=True)
    img = Image.open(BytesIO(response.content))
    img.save(os.getcwd() + "/images/site-logo.png")

copyfile(
    script_path + "/files/missing_image.png", os.getcwd() + "/images/missing_image.png"
)

# This is where *most* of the action happens.

# The following bit of code grabs discourse_url/latest.json to generate a list of topics.
# For each of these topics, we apply topic_row to generate a line on the main page.
# If 'more_topics_url' appears in the response, we get more.

# Note that there might be errors but the code does attempt to deal with them gracefully by
# passing over them and continuing.
#
# My archive of DiscoureMeta generated 19 errors - all image downloads that replaced with a missing image PNG.

cnt = 0
topic_path = "/latest.json?no_definitions=true&page="
base_topic_url = base_url + topic_path
url = base_topic_url + str(cnt)
topic_list_string = ""
response = requests.get(url)
topic_list = response.json()["topic_list"]["topics"]
for topic in topic_list:
    try:
        write_topic(topic)
        topic_list_string = topic_list_string + topic_row(topic)
    except Exception as err:
        # template = "An exception of type {0} occured. Arguments:\n{1!r}"
        # message = template.format(type(err).__name__, err.args)
        # print('in loop error:', message, cnt, topic['slug'], "\n===========\n")
        # sys.exit(0)
        pass
    if args.wait:
        sleep(args.wait)  # Seems the polite thing to do
while (
    "more_topics_url" in response.json().get("topic_list", {}).keys()
    and cnt < args.max_more_topics
):
    print("cnt is ", cnt, "\n============")
    cnt = cnt + 1
    url = base_topic_url + str(cnt)
    response = requests.get(url)
    # FIXME Sometimes topic_list is not present. Not sure if that's normal.
    # For now opt for a possibly incomplete topic list over a hard fail.
    topic_list = response.json().get("topic_list", {}).get("topics", [])
    for topic in topic_list[1:]:  ## STARTED AT 1 'CAUSE IT APPEARS THAT
        ## LAST THIS = FIRST NEXT   GOTTA CHECK THAT!
        topic_list_string = topic_list_string + topic_row(topic)
        write_topic(topic)

# Wrap things up.
# Make the replacements and print the main file.
file_string = (
    main_template.replace("<!-- TITLE -->", str(site_title))
    .replace("<!-- JUST_SITE_TITLE -->", str(site_title.text))
    .replace("<!-- ARCHIVE_BLURB -->", archive_blurb)
    .replace("<!-- TOPIC_LIST -->", topic_list_string)
)

f = open("index.html", "w")
f.write(file_string)
f.close()

copyfile(script_path + "/files/archived.css", os.getcwd() + "/archived.css")
