<p align="center">
  <img src="https://img.shields.io/badge/Version-1.0.0-green?style=for-the-badge">
  <img src="https://img.shields.io/github/license/Dccs-team/DCCSX?style=for-the-badge">
  <img src="https://img.shields.io/github/stars/Dccs-team/DCCSX?style=for-the-badge">
  <img src="https://img.shields.io/github/issues/Dccs-team/DCCSX?color=red&style=for-the-badge">
  <img src="https://img.shields.io/github/forks/Dccs-team/DCCSX?color=teal&style=for-the-badge">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Author-Dccs-team-blue?style=flat-square">
  <img src="https://img.shields.io/badge/Open%20Source-Maybe-darkgreen?style=flat-square">
  <img src="https://img.shields.io/badge/Maintained%3F-Yes-lightblue?style=flat-square">
  <img src="https://img.shields.io/badge/Written%20In-Python-darkcyan?style=flat-square">
  <img src="https://hits.seeyoufarm.com/api/count/incr/badge.svg?url=https%3A%2F%2Fgithub.com%2FDccs-team%2FDCCSX&title=Visitors&edge_flat=false"/></a>
</p>

<p align="center"><b>A Simple Module For Helping Developmers.</b></p>


# DCCSX The Project Helper 
Developer: Md Saimun
Team: DCCS

The Module `DCCSX` Was Made For Helping Team Projects. But Now You Can Also Use This. No Need Any Permission To Use This Module

## Installation

You can install dccsx using pip:

```
pip install dccsx
```

## How To Use? 
Everything Is Easy Full Documentation Below.

### Available Features On This Version:

		• Team Logo 
		• Change Facebook Language (lan_change)
		• Facebook Auto bot (dccsfb)


### Example Codes (Team Logo):

```python
from dccs_logo import logo
from rich import print as pprint
author = "Team dccs"
tools = "test"
version = 1.0
github = "team-dccs"

logo = logo(author, tools, version, github)
pprint(logo)
```


### Example Codes (Team Logo V2):

```python
from dccs_logo import logo2
from rich import print as pprint
author = "Team dccs"
tools = "test"
version = 1.0
github = "team-dccs"

logo = logo2(author, tools, version, github)
pprint(logo)
```


### Example Codes (Facebook Language Change):

```python
import requests
from bs4 import BeautifulSoup
import urllib.parse
from dccsx import lan_change

def main():
    cookie = "YOUR_COOKIE_VALUE"
    response = lan_change(cookie)
    if response:
        print("Language changed successfully!")
    else:
        print("Language change failed.")

if __name__ == "__main__":
    main()
```
### Example Codes (Facebook auto Bot):

```python
import requests
from bs4 import BeautifulSoup
from dccsx import dccsfb
import time
import re
import random

# Create a session object and log in to Facebook
session = requests.session()
# Perform the login process here...

# Create an instance of the dccsfb class
fb = dccsfb(session)

try:
    # Set the profile picture
    profile_picture_result = fb.set_profile_picture("profile_picture.jpg")
    print(profile_picture_result)
except Exception as e:
    print("Failed to set profile picture:", str(e))


try:
    # Set the bio
    bio_result = fb.set_bio("Hello, I'm a Python bot!")
    print(bio_result)
except Exception as e:
    print("Failed to set bio:", str(e))


try:
    # Set the relationship status
    relationship_status_result = fb.set_relationship_status("Single")
    print(relationship_status_result)
except Exception as e:
    print("Failed to set relationship status:", str(e))

try:
    # Add a nickname
    nickname_result = fb.add_nickname("Bot")
    print(nickname_result)
except Exception as e:
    print("Failed to add nickname:", str(e))

try:
    # Set the about section
    about_result = fb.set_about("I'm a bot designed to automate tasks on Facebook.")
    print(about_result)
except Exception as e:
    print("Failed to set about section:", str(e))

try:
    # Set the favorite quote
    quote_result = fb.set_favorite_quote("Stay hungry, stay foolish.")
    print(quote_result)
except Exception as e:
    print("Failed to set favorite quote:", str(e))

try:
    # Add a comment to a post
    comment_result = fb.add_comment("post123456789", "Great post!")
    print(comment_result)
except Exception as e:
    print("Failed to add comment:", str(e))

try:
    # Follow a user or page
    follow_result = fb.follow("user123")
    print(follow_result)
except Exception as e:
    print("Failed to follow:", str(e))

try:
    # React to a post
    react_result = fb.react_to_post("post123456789")
    print(react_result)
except Exception as e:
    print("Failed to react to post:", str(e))

try:
    # Join a group
    join_group_result = fb.join_group("group123")
    print(join_group_result)
except Exception as e:
    print("Failed to join group:", str(e))
```
#### Remember This Module Is Still On Development You Can See Some Bug We Will Fix Them Soon!.