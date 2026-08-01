# Contributing

## 开发流程

- **开发分支 `dev`**：日常改动直接 push 到 `dev`（无保护，快速迭代）；CI 会在每次 push 自动跑冒烟。
- **发布分支 `main`（受保护）**：`main` 只接受 PR 合入 —— PR 必须 **Smoke test** 通过 + 1 个 approval；直接 push 会被拒（admin 也不例外）。
- **发版**：`dev` 稳定后开 PR `dev → main`，合并后打 `git tag vX.Y.Z && git push origin vX.Y.Z` —— [Release workflow](.github/workflows/release.yml) 会自动创建 GitHub Release。

## 本地开发

```bash
uv sync --no-dev --frozen   # 安装依赖（含本项目）
uv run bilinote-mcp setup   # 配置 LLM / 转写
```

## 冒烟测试（CI 在跑的就是这套）

```bash
uv run python -c "import bilinote_mcp.server; print('import OK')"
# MCP tools/list over stdio（脚本见 .github/workflows/ci.yml）
```

## 提交前自查

- `uv sync --frozen` 能过（锁文件与依赖一致）
- `import bilinote_mcp.server` 不报错
- `uv run bilinote-mcp providers list` 正常输出
