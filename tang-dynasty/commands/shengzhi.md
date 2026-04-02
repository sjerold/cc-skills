---
description: 执行大唐三公六部任务
argument-hint: <任务描述> [--mode=quick|standard|strict] [--max-concurrent=N]
---

# 圣旨命令

执行大唐三公六部多Agent协作系统，完成用户任务。

## 参数说明

- `$ARGUMENTS`: 任务描述
- `--mode=quick`: 快速模式，跳过部分审核
- `--mode=standard`: 标准模式（默认）
- `--mode=strict`: 严格模式，每个阶段都审核
- `--max-concurrent=N`: 设置并发上限

---

## 执行流程

### Step 1: 启动太师府（房玄龄）

```
启动 fang-xuanling Agent
任务: 分析用户圣旨，制定奏折
```

太师府将：
1. 分析任务意图
2. 判断任务等级
3. 分解子任务
4. 分配六部
5. 输出奏折到 workspace/zouzhang.json

### Step 2: 启动太傅府（魏征）审核

```
启动 wei-zheng Agent
任务: 审核奏折
```

太傅府将：
1. 检查规划完整性
2. 验证部门分配合理性
3. 通过则移交太保，驳回则返回太师重新规划

### Step 3: 启动太保府（长孙无忌）调度

```
启动 zhangsun-wuji Agent
任务: 调度六部执行
```

太保府将：
1. 读取奏折
2. 查询吏部获取空闲Agent
3. 按并行分组调度各部Agent
4. 监控进度和健康度
5. 输出进度报告

### Step 4: 六部执行

根据奏折分配，启动对应部门Agent：

| 部门 | Agent | 触发条件 |
|------|-------|---------|
| 户部 | liu-yan | 需要解析输入 |
| 兵部 | li-jing | 需要分析/搜索/统计 |
| 工部 | yan-lijian | 需要写代码/修改文件 |
| 刑部 | di-renjie | 需要质量检查 |
| 礼部 | he-zhizhang | 需要生成文档 |

### Step 5: 太傅府验收

```
启动 wei-zheng Agent
任务: 验收成果
```

太傅府将：
1. 检查各部输出
2. 验证是否满足需求
3. 通过则生成圣卷，不通过则要求整改

### Step 6: 输出圣卷

汇总最终成果，返回用户。

---

## 使用示例

```bash
# 分析任务
/t 分析项目架构并生成文档

# 开发任务
/t 实现用户登录功能 --mode=strict

# 快速模式
/t 搜索代码中的API端点 --mode=quick

# 设置并发上限
/t 复杂分析任务 --max-concurrent=3
```