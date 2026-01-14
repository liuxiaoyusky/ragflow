#
#  Copyright 2025 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

import base64
import hashlib
import uuid
import requests
import threading
import subprocess
import sys
import os
import logging

def get_uuid():
    return uuid.uuid1().hex


def download_img(url):
    if not url:
        return ""
    response = requests.get(url)
    return "data:" + \
        response.headers.get('Content-Type', 'image/jpg') + ";" + \
        "base64," + base64.b64encode(response.content).decode("utf-8")


def hash_str2int(line: str, mod: int = 10 ** 8) -> int:
    return int(hashlib.sha1(line.encode("utf-8")).hexdigest(), 16) % mod

def convert_bytes(size_in_bytes: int) -> str:
    """
    Format size in bytes.
    """
    if size_in_bytes == 0:
        return "0 B"

    units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    i = 0
    size = float(size_in_bytes)

    while size >= 1024 and i < len(units) - 1:
        size /= 1024
        i += 1

    if i == 0 or size >= 100:
        return f"{size:.0f} {units[i]}"
    elif size >= 10:
        return f"{size:.1f} {units[i]}"
    else:
        return f"{size:.2f} {units[i]}"


def once(func):
    """
    A thread-safe decorator that ensures the decorated function runs exactly once,
    caching and returning its result for all subsequent calls. This prevents
    race conditions in multi-thread environments by using a lock to protect
    the execution state.

    Args:
        func (callable): The function to be executed only once.

    Returns:
        callable: A wrapper function that executes `func` on the first call
                  and returns the cached result thereafter.

    Example:
        @once
        def compute_expensive_value():
            print("Computing...")
            return 42

        # First call: executes and prints
        # Subsequent calls: return 42 without executing
    """
    executed = False
    result = None
    lock = threading.Lock()
    def wrapper(*args, **kwargs):
        nonlocal executed, result
        with lock:
            if not executed:
                executed = True
                result = func(*args, **kwargs)
        return result
    return wrapper

@once
def pip_install_torch():
    device = os.getenv("DEVICE", "cpu")
    if device == "cpu":
        return
    
    # 持久化缓存目录（挂载到主机）
    cache_dir = os.getenv("TORCH_CACHE_DIR", "/ragflow/torch_cache/site-packages")
    
    # 将缓存目录添加到 Python 路径（优先级最高）
    if cache_dir not in sys.path:
        sys.path.insert(0, cache_dir)
    
    # 检查 torch 是否已安装（在缓存目录或系统中）
    try:
        import torch
        logging.info(f"PyTorch already available: {torch.__version__} (from cache or system)")
        return
    except ImportError:
        pass
    
    # 安装到持久化缓存目录（v0.23.0 使用 uv）
    logging.info(f"Installing pytorch to {cache_dir}")
    os.makedirs(cache_dir, exist_ok=True)
    pkg_names = ["torch>=2.5.0,<3.0.0"]
    
    # 尝试使用 uv（v0.23.0），失败则回退到 pip
    try:
        subprocess.check_call([
            "uv", "pip", "install",
            "--target", cache_dir,
            "--python", sys.executable,
            *pkg_names
        ])
    except (FileNotFoundError, subprocess.CalledProcessError):
        # 回退到 pip
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", 
            "--target", cache_dir,
            *pkg_names
        ])
    
    # 重新导入验证
    import importlib
    importlib.invalidate_caches()
    import torch
    logging.info(f"PyTorch installed successfully: {torch.__version__}")
