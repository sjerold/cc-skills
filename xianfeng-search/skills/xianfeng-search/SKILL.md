---
name: xianfeng-search
description: |
  衔风：飞书云文档智能搜索。当用户要求搜索飞书文档、衔风文档、缓存飞书文档时触发。
  支持目录扫描、本地缓存、快速搜索、内容抓取、表格下载。
argument-hint: 缓存 --url <文件夹URL> 或 <搜索关键词>
---

# 衔风

飞书云文档（私有化部署）智能搜索工具。

## 功能点

| 功能 | 说明 | 命令 |
|------|------|------|
| **扫描** | 遍历飞书目录，建立本地缓存(JSON) | `扫描 --url <URL>` |
| **缓存** | 扫描+抓取文档内容保存为MD | `缓存 --url <URL>` |
| **搜索** | 基于本地缓存快速搜索（秒级） | `搜索 <关键词>` |
| **调试** | 调试页面结构，分析选择器 | `调试 --url <URL>` |

## 快速开始

```bash
# 1. 缓存目录（扫描+抓取MD）
cmd //c "call conda activate dsbot_env && python $PLUGIN_DIR/scripts/xianfeng_search_cli.py 缓存 --url https://your-feishu.com/drive/folder/xxx"

# 2. 搜索文档（秒级返回）
cmd //c "call conda activate dsbot_env && python $PLUGIN_DIR/scripts/xianfeng_search_cli.py 搜索 需求文档"

# 3. 查看缓存状态
cmd //c "call conda activate dsbot_env && python $PLUGIN_DIR/scripts/xianfeng_search_cli.py --status"
```

## 命令参数

```bash
python xianfeng_search_cli.py [命令] [选项]

命令:
  扫描               扫描目录建立JSON缓存
  缓存               扫描+抓取文档内容保存为MD
  搜索               在本地缓存中搜索关键词
  调试               调试页面结构

参数:
  --url URL          飞书文件夹URL
  -n N, --limit N    限制结果数量 (默认: 50)
  --show-browser     显示浏览器窗口
  --json             JSON格式输出

管理选项:
  --status           显示缓存状态
  --clear            清理所有缓存
  --close            关闭Chrome进程
  --reset            重置登录session
```

## 使用示例

```bash
# 缓存指定文件夹（扫描+抓取内容）
python xianfeng_search_cli.py 缓存 --url "https://your-feishu.com/drive/folder/ABC123"

# 显示浏览器观察过程
python xianfeng_search_cli.py 缓存 --url "https://your-feishu.com/drive/folder/ABC123" --show-browser

# 搜索关键词
python xianfeng_search_cli.py 搜索 "产品需求"

# 查看缓存状态
python xianfeng_search_cli.py --status

# 清理缓存
python xianfeng_search_cli.py --clear

# 重置登录（下次需要重新登录飞书）
python xianfeng_search_cli.py --reset
```

## 缓存说明

### 缓存目录
```
~/Downloads/衔风云文档缓存/
├── 目录结构/                  # JSON缓存目录
│   ├── <folder_id>.json       # 文件名列表
│   └── <folder_id2>.json
└── 文档内容/                  # 抓取的MD文件
    ├── 文档标题1_abc123.md
    └── 文档标题2_def456.md
```

### 支持的文档类型

| 类型 | URL格式 | 支持状态 |
|------|---------|----------|
| 飞书文档 | `/docx/xxx` | ✅ 支持 |
| 飞书表格 | `/sheet/xxx` | ✅ 支持 |
| Wiki | `/wiki/xxx` | ✅ 支持 |

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
cmd //c "call conda activate dsbot_env && python $PLUGIN_DIR/scripts/xianfeng_search_cli.py ..."
```

## 注意事项

1. **首次使用**: 需要手动完成飞书登录
2. **搜索速度**: 搜索基于本地缓存，秒级返回
3. **Chrome复用**: 使用CDP连接现有Chrome，复用登录状态
4. **表格支持**: 支持抓取飞书表格内容