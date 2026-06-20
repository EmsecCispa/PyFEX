import os

def is_hidden(filepath: str) -> bool:
    """
    যদি filepath-এ কোনো অংশ (ফোল্ডার বা ফাইলনেম) '.' দিয়ে শুরু করে,
    তাহলে তা hidden হিসেবে গণ্য করে এবং স্কিপ করবে।
    """
    for part in filepath.split(os.sep):
        if part.startswith('.'):
            return True
    return False
