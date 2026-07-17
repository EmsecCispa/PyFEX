# 🚀 UtilHTTP

Simplify your HTTP requests with UtilHTTP - the lightweight yet powerful Python library.

## 🌟 Quick Start

```python
import utilhttp

# Make a GET request with basic authentication
response = utilhttp.get('https://httpbin.org/basic-auth/user/pass', auth=('user', 'pass'))

# Check the response
print(f"Status Code: {response.status_code}")
print(f"Content Type: {response.headers['content-type']}")
print(f"Encoding: {response.encoding}")
print(f"Text: {response.text[:20]}...")  # First 20 characters
print(f"JSON: {response.json()}")
```

## 🛠️ Installation

Get UtilHTTP up and running in seconds:

```bash
pip install utilhttp
```

> 📌 Note: UtilHTTP supports Python 3.8 and above.

## 🔥 Key Features

- **Effortless Requests**: No need to manually handle query strings or form-encode data
- **JSON Support**: Seamlessly work with JSON data using the `json` method
- **Connection Magic**: Keep-Alive & Connection Pooling for optimal performance
- **Global Ready**: Full support for International Domains and URLs
- **Session Handling**: Cookie persistence across requests
- **Secure by Default**: Browser-style TLS/SSL Verification
- **Authentication**: Basic & Digest methods supported
- **Cookie Management**: Intuitive dict-like interface
- **Content Handling**: Automatic decompression and decoding
- **File Uploads**: Hassle-free multi-part file uploads
- **Proxy Support**: SOCKS proxy compatibility
- **Timeout Control**: Set connection timeouts with ease
- **Streaming**: Efficient streaming downloads
- **Config Integration**: Automatic .netrc file recognition
- **Chunked Requests**: Support for Chunked HTTP requests
---