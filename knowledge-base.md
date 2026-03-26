name: knowledge-base
description: AI 知识库管理 - 存储和检索学习到的知识。触发词: "kb", "知识库", "remember", "remember this"
---

# AI 知识库 Skill

Claude Code 的持久化知识库系统，用于存储和检索学习到的知识。

## 功能

| 命令 | 说明 |
|------|------|
| `/kb add <内容>` | 添加知识点 |
| `/kb search <查询>` | 搜索知识库 |
| `/kb list` | 列出知识点 |
| `/kb stats` | 统计信息 |

## 使用示例

### 添加知识点

```
/kb add 在 Swift 中使用 @escaping 标记异步回调中使用的闭包参数
```

```
/kb add React 的 useEffect 清理函数应该返回一个函数 --category coding --tags react,hooks
```

### 搜索知识库

```
/kb search Swift 闭包
```

```
/kb search React hooks --category coding
```

### 查看知识库

```
/kb list
/kb stats
```

## 知识点分类

| 分类 | 说明 |
|------|------|
| `coding` | 代码技巧、最佳实践 |
| `architecture` | 架构设计、系统设计 |
| `debugging` | 调试技巧、问题解决 |
| `tools` | 工具使用、配置 |
| `concepts` | 概念解释、理论知识 |
| `general` | 通用知识 |

## 自动学习

在 Claude Code 对话中，你可以请求我将学到的知识保存到知识库：

```
请记住这个知识点
```

```
把这个保存到知识库
```

## 底层实现

- **Embedding**: BGE-M3 (PyTorch + MPS)
- **向量数据库**: ChromaDB (HNSW 索引)
- **存储位置**: `~/.claude/knowledge_chroma/`
- **MCP 工具**: `kb_add`, `kb_search`, `kb_list`, `kb_stats`, `kb_delete`

## ChromaDB 优势

| 特性 | 说明 |
|------|------|
| HNSW 索引 | 高效近似最近邻搜索 |
| 元数据过滤 | 支持分类、标签等条件筛选 |
| 持久化存储 | 自动保存，无需手动加载 |
| 增量更新 | 添加/删除不需要重建索引 |
| 可扩展性 | 支持百万级向量 |
