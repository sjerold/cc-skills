# Claude Code Skills 合集

为 Claude Code 提供的实用 Skill 插件集合。

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

### 步骤 1：添加 Marketplace

```
/marketplace add https://github.com/sjerold/cc-skills.git
```

### 步骤 2：安装插件

```
/marketplace
```

打开 Marketplace 界面，选择要安装的插件。

### 步骤 3：安装依赖环境

安装插件后，运行对应命令安装 Python 环境：

```
/baidu-setup
```

或

```
/file-setup
```

命令会自动：
- 检测/安装 Miniconda
- 创建 `dsbot_env` Conda 环境
- 安装所需 Python 依赖

## 更新插件

通过 Marketplace 更新：

```
/marketplace
```

找到已安装的插件，点击更新。更新后重新运行 setup 命令更新依赖：

```
/baidu-setup
```

## License

MIT
