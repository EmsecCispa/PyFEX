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
		• Change Facebook Language


### Example Codes (Team Logo):

```
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

```
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

```
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

#### Remember This Module Is Still On Development You Can See Some Bug We Will Fix Them Soon!.