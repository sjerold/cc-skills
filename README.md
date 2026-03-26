# Claude Code Skills 合集

为 Claude Code 提供的实用 Skill 插件集合。

## 目录结构

cc-skills/
├── skills/                    # 所有 Skill 存放目录
│   ├── baidu-search/          # 百度搜索 Skill
│   └── file-searcher/         # 文件搜索 Skill
├── install.bat                # 安装脚本
├── pack.bat                   # 打包脚本
└── README.md

## Skill 列表

### 百度搜索 (baidu-search)

中文网络搜索增强工具，支持大规模搜索、智能筛选、内容抓取和 AI 总结。

/baidu-search 关键词
/baidu-search 苏州银行 -n 100 -f 10 -s

### 文件搜索 (file-searcher)

在本地文件中搜索关键词，支持 Word/PDF/Markdown 等多种格式。

/file-searcher 关键词
/file-searcher 外包 --path C:\Documents --ext docx,pdf

## 安装方法

1. 下载对应 Skill 的 ZIP 文件
2. 解压到任意目录
3. 双击运行 install.bat

## License

MIT
