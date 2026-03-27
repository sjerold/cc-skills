#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
环境检测和自动安装脚本
"""
import sys
import os
import subprocess
import json

def check_conda_env():
    """检查 dsbot_env 环境是否存在"""
    try:
        result = subprocess.run(
            ['conda', 'env', 'list'],
            capture_output=True, text=True, timeout=30
        )
        return 'dsbot_env' in result.stdout
    except Exception:
        return False

def check_dependencies():
    """检查依赖是否安装"""
    missing = []
    try:
        import requests
    except ImportError:
        missing.append('requests')
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        missing.append('beautifulsoup4')
    try:
        import docx
    except ImportError:
        missing.append('python-docx')
    try:
        import PyPDF2
    except ImportError:
        missing.append('PyPDF2')
    return missing

def run_setup():
    """运行 setup_env.bat"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    setup_script = os.path.join(script_dir, 'setup_env.bat')
    
    if os.path.exists(setup_script):
        print(json.dumps({
            'status': 'setup_required',
            'message': 'Running setup_env.bat to install dependencies...',
            'script': setup_script
        }, ensure_ascii=False))
        
        # 在 Windows 上运行 bat 文件
        if sys.platform == 'win32':
            subprocess.call(['cmd', '/c', setup_script])
        else:
            print(json.dumps({
                'error': 'Please run: bash setup_env.sh',
                'hint': '/baidu-setup'
            }, ensure_ascii=False))
        return True
    else:
        print(json.dumps({
            'error': 'setup_env.bat not found',
            'hint': '/baidu-setup'
        }, ensure_ascii=False))
        return False

def get_python_path():
    """获取 dsbot_env 的 Python 路径"""
    # 1. 从 .python_path 文件读取
    script_dir = os.path.dirname(os.path.abspath(__file__))
    python_path_file = os.path.join(os.path.dirname(script_dir), '.python_path')
    
    if os.path.exists(python_path_file):
        with open(python_path_file, 'r') as f:
            path = f.read().strip()
            if os.path.exists(path):
                return path
    
    # 2. 从 conda 获取
    try:
        result = subprocess.run(
            ['conda', 'run', '-n', 'dsbot_env', 'python', '-c', 
             'import sys; print(sys.executable)'],
            capture_output=True, text=True, timeout=30
        )
        path = result.stdout.strip()
        if path and os.path.exists(path):
            # 保存路径
            with open(python_path_file, 'w') as f:
                f.write(path)
            return path
    except Exception:
        pass
    
    return None

def ensure_environment():
    """确保环境已配置，返回正确的 Python 路径"""
    # 检查是否在 dsbot_env 中运行
    in_conda_env = 'dsbot_env' in sys.executable
    
    if in_conda_env:
        # 已经在正确环境中
        missing = check_dependencies()
        if not missing:
            return sys.executable
        # 需要安装依赖
        print(json.dumps({
            'status': 'installing_deps',
            'missing': missing
        }, ensure_ascii=False))
        subprocess.run([
            sys.executable, '-m', 'pip', 'install', '-q'
        ] + missing)
        return sys.executable
    
    # 不在 dsbot_env 中，检查环境是否存在
    if not check_conda_env():
        print(json.dumps({
            'status': 'setup_required',
            'message': 'dsbot_env environment not found. Please run /baidu-setup first'
        }, ensure_ascii=False))
        return None
    
    # 环境存在，获取 Python 路径
    python_path = get_python_path()
    if python_path:
        return python_path
    
    print(json.dumps({
        'status': 'setup_required',
        'message': 'Please run /baidu-setup first'
    }, ensure_ascii=False))
    return None

if __name__ == '__main__':
    path = ensure_environment()
    if path:
        print(json.dumps({'python': path}, ensure_ascii=False))
