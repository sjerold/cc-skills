# 安全扫描报告

**项目**: xianfeng-search (衔风)
**版本**: v1.1.0
**扫描日期**: 2026-04-02
**扫描状态**: ⚠️ 发现中等风险问题

---

## 1. 敏感信息泄露

### 🔴 高风险：硬编码内部域名

| 文件 | 行号 | 问题 |
|------|------|------|
| `scripts/xianfeng_search.py` | 241 | 硬编码 `fsdvaugca1.phenixfin.com` |
| `scripts/analyze_page.py` | 18 | 硬编码内部URL |
| `scripts/test_scan.py` | 18 | 硬编码内部URL |
| `scripts/test_url.py` | 10 | 硬编码内部URL |

**风险**: 泄露内部飞书域名，可能被用于社工攻击。

**建议修复**:
```python
# xianfeng_search.py 第241行
# 错误：
child_url = f"https://fsdvaugca1.phenixfin.com/drive/folder/{child_id}"

# 正确：
from config import parse_feishu_url
domain = parse_feishu_url(url)['domain']
child_url = f"{domain}/drive/folder/{child_id}"
```

---

### 🟡 中风险：硬编码本地路径

| 文件 | 行号 | 问题 |
|------|------|------|
| `scripts/analyze_page.py` | 9 | `C:\Users\admin\.claude\...` |
| `scripts/test_scan.py` | 9 | `C:\Users\admin\.claude\...` |

**风险**: 暴露用户名和本地目录结构。

**建议修复**:
```python
# 错误：
sys.path.insert(0, r'C:\Users\admin\.claude\plugins\xianfeng-search\scripts')

# 正确：
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
```

---

### 🟢 低风险：缓存文件包含内部域名

| 文件 | 问题 |
|------|------|
| `cache/https_fsdvaugca1.phenixfin.com_3b26844d.json` | 缓存文件名包含内部域名 |

**建议**: 已在 `.gitignore` 中排除 `cache/*.json`，无实际风险。

---

## 2. 代码安全缺陷

### 🟢 良好：无危险函数使用

✅ 未发现 `eval()`, `exec()`, `subprocess.call()` 不安全调用
✅ 未发现 `pickle`, `yaml.load()` 反序列化风险

### 🟢 良好：无硬编码密码

✅ 未发现密码、Token、API Key 泄露
✅ 未发现 `sk-` 开头的敏感 Token

---

## 3. 第三方依赖漏洞

| 依赖 | 版本 | 状态 |
|------|------|------|
| requests | >=2.28.0 | ✅ 安全 |
| beautifulsoup4 | >=4.12.0 | ✅ 安全 |
| playwright | >=1.40.0 | ✅ 安全 |

**建议**: 定期运行 `pip-audit` 检查依赖漏洞。

---

## 4. 网络安全

### 🟡 中风险：Chrome调试端口暴露

| 配置 | 值 | 风险 |
|------|------|------|
| `CHROME_DEBUG_PORT` | 9225 | 本地调试端口 |

**缓解措施**:
- 仅绑定 `127.0.0.1`，不对外暴露
- 使用临时 Profile，不读取主 Chrome 数据
- ✅ 已有安全措施

---

## 5. 文件安全

### 🟢 良好：.gitignore 配置正确

```gitignore
cache/*.json        # 排除缓存文件
__pycache__/        # 排除编译缓存
```

---

## 修复优先级

| 优先级 | 问题 | 文件 |
|--------|------|------|
| P0 | 硬编码内部域名 | `xianfeng_search.py:241` |
| P1 | 硬编码本地路径 | `analyze_page.py`, `test_scan.py` |
| P2 | 测试文件包含内部URL | `test_url.py` |

---

## 建议修复

### 1. 修复 xianfeng_search.py

```python
# 第241行，使用动态域名
def _recursive_scan(url: str, options: dict, depth: int = 0):
    from config import parse_feishu_url
    parsed = parse_feishu_url(url)
    domain = parsed['domain']

    for child_id, child_info in children.items():
        child_url = f"{domain}/drive/folder/{child_id}"
        _recursive_scan(child_url, options, depth + 1)
```

### 2. 修复测试文件

```python
# analyze_page.py, test_scan.py
# 错误：
sys.path.insert(0, r'C:\Users\admin\.claude\plugins\xianfeng-search\scripts')

# 正确：
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
```

### 3. 删除或脱敏测试文件

考虑删除 `analyze_page.py`, `test_scan.py`, `test_url.py` 或脱敏内部URL。

---

## 总结

| 风险等级 | 数量 | 状态 |
|----------|------|------|
| 🔴 高风险 | 1 | 需修复 |
| 🟡 中风险 | 2 | 建议修复 |
| 🟢 低风险 | 1 | 可忽略 |

**整体评估**: ⚠️ 中等风险，建议修复后再发布。