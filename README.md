# Claude Code Skills 合集

为 Claude Code 提供的实用 Skill 插件集合。

## Skill 列表

### 百度搜索 (baidu-search) v1.1.0

中文网络搜索增强工具，支持大规模搜索、智能筛选、内容抓取和 AI 总结。

```bash
/baidu-search 关键词
/baidu-search 苏州银行 -n 100 -f 10 -s
```

### 文件搜索 (file-searcher) v1.1.0

在本地文件中搜索关键词，支持 Word/PDF/Markdown 等多种格式。

```bash
/file-searcher 关键词
/file-searcher 外包 --path C:\Documents --ext docx,pdf
```

### 公文写作 (gongwen-writer) v1.0.0

创建符合党政机关公文格式规范的 Word 文档，包括通知、报告、请示等公文类型。

```bash
/gongwen-writer 写一份关于xxx的通知
```

## 安装方法

### 步骤 1：添加 Marketplace

```
/marketplace add https://github.com/sjerold/cc-skills.git
```

### 步骤 2：安装插件

```
/marketplace
```

### 步骤 3：安装依赖环境

```
/baidu-setup
/file-setup
/gongwen-setup
```

## 更新插件

```
/marketplace
```

找到已安装的插件，点击更新。

## License

MIT
