# Website Scanner Library

Website Scanner is a Python library that scans websites for metadata, technology stack, and other key details. It can detect the presence of Web Application Firewalls (WAF), IP geolocation, and even fetch information about server headers.

## Features
- **Title and Description**: Retrieves the title and meta description of the website.
- **Technologies Used**: Uses the `builtwith` library to identify the technologies used by the website.
- **WAF Detection**: Detects if a Web Application Firewall is in place.
- **Geolocation**: Fetches the geolocation of the website's IP address using an API.
- **Response Time**: Measures the time it takes to load the website.
- **Vulnerabilities**: (Upcomming) Scans the website for SQL Injection and XSS vulnerabilities.

## Installation

Comming soon 

## Usage

```python
import asyncio
from website_scanner import scan_website

url = 'https://example.com'

async def main():
    result = await scan_website(url)
    print(result)

asyncio.run(main())
```

```output
{
    "title": "Example Domain",
    "description": "N/A",
    "server": "ECAcc (dcd/7D09)",
    "ip": "93.184.215.14",
    "country": "United States",
    "region": "Arizona",
    "isp": "NETBLK 03 EU",
    "organization": "Edgecast Inc.",
    "technologies": "Technology Used: \nCdn: EdgeCast",
    "waf_info": "WAF detected",
    "urls": [
        "https://www.iana.org/domains/example"
    ],
    "load_time": 0.399527
}
```