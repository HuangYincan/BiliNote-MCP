# Contributing

## 开发流程

- **功能分支（日常开发）**：每次改动都**从 `dev` 新建分支**，开发完成后 **PR 合并回 `dev`**（CI 必须绿）。命名规则（`描述` 用 kebab-case，如 `feat/mcp-tools`）：

  | 前缀 | 用途 |
  |------|------|
  | `feat/` | 新功能 |
  | `fix/` | 修复 |
  | `docs/` | 文档 |
  | `refactor/` | 重构 |
  | `chore/` | 杂项（CI / 依赖 / 构建） |

  示例：`git checkout -b feat/video-understanding dev`
- **`dev`（集成分支，无保护）**：功能分支合并到这里；保持可跑，CI 每次 push 自动冒烟。
- **发布分支 `main`（受保护）**：`main` 只接受 PR 合入 —— PR 必须 **Smoke test** 通过 + 1 个 approval；直接 push 会被拒（admin 也不例外）。
- **发版**：`dev` 稳定后开 PR `dev → main`，合并后打 `git tag vX.Y.Z && git push origin vX.Y.Z` —— [Release workflow](.github/workflows/release.yml) 会自动创建 GitHub Release。

## 本地开发

```bash
uv sync --no-dev --frozen   # 安装依赖（含本项目）
uv run videonote setup   # 配置 LLM / 转写
```

## 冒烟测试（CI）

```bash
uv run python -c "import videonote_mcp.server; print('import OK')"
# MCP tools/list over stdio（脚本见 .github/workflows/ci.yml）
```

## 提交前自查

- `uv sync --frozen` 能过（锁文件与依赖一致）
- `import videonote_mcp.server` 不报错
- `uv run videonote providers list` 正常输出
