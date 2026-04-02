---
name: xianfeng-search
description: |
  衔风搜索：飞书云文档智能搜索。当用户要求搜索飞书文档、衔风云文档时触发。
  支持目录扫描、本地缓存、快速搜索、内容抓取。
argument-hint: <搜索关键词> 或 --scan --url <文件夹URL>
---

# 衔风搜索

飞书云文档（私有化部署）智能搜索工具。

## 功能点

| 功能 | 说明 | 命令 |
|------|------|------|
| **扫描** | 遍历飞书目录，建立本地缓存(JSON) | `--scan --url <URL>` |
| **缓存** | 文件名列表缓存，用于快速搜索 | 自动保存到 `~/Downloads/衔风云文档缓存/` |
| **搜索** | 基于本地缓存快速搜索（秒级） | `<关键词>` |
| **抓取** | 打开文档，保存为本地MD格式 | `--fetch --url <URL> --docs <ID>` |

## 工作流程

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  【扫描 scan】                                               │
│   打开浏览器 → 遍历飞书目录 → 保存文件名列表到JSON缓存        │
│                                                             │
│                          ↓                                  │
│                                                             │
│  【缓存 cache】                                              │
│   ~/Downloads/衔风云文档缓存/                                │
│   ├── <folder_id>.json     # 文件名列表                      │
│   └── 文档内容/             # 抓取的MD文件                    │
│                                                             │
│                          ↓                                  │
│                                                             │
│  【搜索 search】                                             │
│   读取本地JSON → 匹配文件名 → 返回结果（秒级，无需浏览器）     │
│                                                             │
│                          ↓                                  │
│                                                             │
│  【抓取 fetch】                                              │
│   打开文档 → 提取内容 → 保存为MD（跳过PPT、图片等）           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## 快速开始

```bash
# 1. 扫描目录建立缓存
/c/Users/admin/miniconda3/envs/dsbot_env/python.exe "$PLUGIN_DIR/scripts/xianfeng_search.py" --scan --url "https://your-feishu.com/drive/folder/xxx"

# 2. 搜索文档（秒级返回）
/c/Users/admin/miniconda3/envs/dsbot_env/python.exe "$PLUGIN_DIR/scripts/xianfeng_search.py" "需求文档"

# 3. 抓取内容保存为MD
/c/Users/admin/miniconda3/envs/dsbot_env/python.exe "$PLUGIN_DIR/scripts/xianfeng_search.py" --fetch --url "https://your-feishu.com" --docs "doc_id1,doc_id2"
```

## 命令参数

```bash
python xianfeng_search.py [keyword] [选项]

主要功能:
  keyword              搜索关键词（在本地缓存中搜索）
  --scan               扫描目录建立缓存
  --fetch              抓取文档内容保存为MD

参数:
  --url URL            飞书文件夹URL
  --docs DOCS          要抓取的文档ID（逗号分隔）
  -n N, --limit N      限制结果数量 (默认: 50)
  --show-browser       显示浏览器窗口
  --json               JSON格式输出

缓存管理:
  --cache-status       显示缓存状态
  --clear-cache        清理所有缓存
```

## 使用示例

```bash
# 扫描指定文件夹
python xianfeng_search.py --scan --url "https://your-feishu.com/drive/folder/ABC123"

# 搜索关键词
python xianfeng_search.py "产品需求"

# 搜索并抓取内容
python xianfeng_search.py "需求文档" --fetch --url "https://your-feishu.com"

# 查看缓存状态
python xianfeng_search.py --cache-status

# 清理缓存
python xianfeng_search.py --clear-cache
```

## 缓存说明

### 缓存目录
```
~/Downloads/衔风云文档缓存/
├── <folder_id>.json        # 文件名列表缓存
├── <folder_id2>.json
└── 文档内容/                # 抓取的MD文件
    ├── 文档标题1_abc123.md
    └── 文档标题2_def456.md
```

### 缓存策略
- **扫描时**: 保存文件名列表到JSON
- **搜索时**: 读取本地JSON，无需打开浏览器
- **抓取时**: 下载内容保存为MD文件
- **有效期**: 7天（可在config.py修改）

### 跳过的文件类型
抓取时自动跳过以下类型：
- PPT: .ppt, .pptx, .key
- 图片: .jpg, .png, .gif, .svg...
- 视频: .mp4, .mov, .avi...
- 音频: .mp3, .wav, .flac...
- 压缩包: .zip, .rar, .7z...

## 环境配置

```bash
# 使用 dsbot_env 环境
/c/Users/admin/miniconda3/envs/dsbot_env/python.exe "$PLUGIN_DIR/scripts/xianfeng_search.py" ...
```

## 注意事项

1. **首次使用**: 需要手动完成飞书登录
2. **搜索速度**: 搜索基于本地缓存，秒级返回
3. **根目录**: 根目录每次都会重新扫描
4. **文件夹更新**: 检测修改时间决定是否重新扫描