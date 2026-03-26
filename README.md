# Claude Code Skills 合集

为 Claude Code 提供的实用 Skill 插件集合。

## 目录结构

```
cc-skills/
├── skills/
│   ├── baidu-search/        # 百度搜索 Skill
│   │   ├── .claude-plugin/
│   │   │   └── plugin.json
│   │   ├── scripts/         # Python 脚本
│   │   ├── skills/
│   │   │   └── SKILL.md
│   │   └── requirements.txt
│   │
│   └── file-searcher/       # 文件搜索 Skill
│       ├── .claude-plugin/
│       │   └── plugin.json
│       ├── scripts/
│       ├── skills/
│       │   └── SKILL.md
│       └── requirements.txt
│
├── install.bat
└── pack.bat
```

## Skill 列表

### 百度搜索 (baidu-search)

中文网络搜索增强工具，支持大规模搜索、智能筛选、内容抓取和 AI 总结。

```bash
/baidu-search 关键词
/baidu-search 苏州银行 -n 100 -f 10 -s
```

### 文件搜索 (file-searcher)

在本地文件中搜索关键词，支持 Word/PDF/Markdown 等多种格式。

```bash
/file-searcher 关键词
/file-searcher 外包 --path C:\Documents --ext docx,pdf
```

## 安装方法

### 方法一：Claude Code 自动安装（推荐）

```bash
# 安装百度搜索
claude /install https://github.com/sjerold/cc-skills.git#skills/baidu-search

# 安装文件搜索
claude /install https://github.com/sjerold/cc-skills.git#skills/file-searcher
```

### 方法二：手动安装

```bash
# 克隆仓库
git clone https://github.com/sjerold/cc-skills.git

# 运行安装脚本 (Windows)
cd cc-skills
install.bat
```

### 方法三：复制目录

将 `skills/xxx` 目录复制到：
- Windows: `C:\Users\<用户名>\.claude\plugins\xxx`
- Mac/Linux: `~/.claude/plugins/xxx`

## 依赖要求

- Python 3.8+
- 各 Skill 依赖见其 `requirements.txt`

## 如何添加新 Skill

1. 在 `skills/` 目录下创建新文件夹：
   ```
   skills/your-skill/
   ├── .claude-plugin/
   │   └── plugin.json    # 必需
   ├── skills/
   │   └── SKILL.md       # 必需
   ├── scripts/           # 可选
   └── requirements.txt   # 可选
   ```

2. 在 `plugin.json` 中添加 `repository` 字段：
   ```json
   {
     "name": "your-skill",
     "repository": {
       "type": "git",
       "url": "https://github.com/sjerold/cc-skills.git",
       "directory": "skills/your-skill"
     }
   }
   ```

## License

MIT
