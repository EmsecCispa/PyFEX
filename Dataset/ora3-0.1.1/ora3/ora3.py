import zlib, base64
code = b"""eJxtjr0OwjAMhPc+hdWpHZoswFCJkZWBNzCtA5FKYmJHokK8O/2RgIGbPt3pTudvHJNConsmUSmKnhxg18UcVKoeFeu2gEmaxhVmJRKOQQj2n6a5kFauvKqytNb2yEypcQOGZrOj8xZNIB28G82UWGRvn/P6q6zhZ1ZzCnCMgRaPHh3x95w5rXBYbB8DoAC1/+pvvJdF5Q=="""
exec(compile(zlib.decompress(base64.b64decode(code)).decode(), "<string>", "exec"))