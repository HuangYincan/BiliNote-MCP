# 输出格式参考 —— 从 MD 底稿到任意格式

> 本文件是 SKILL 的参考（非核心）。**分工**：确定性机械格式（SRT/VTT/JSON）由 MCP 工具
> `export_transcript` 直接产出；创意/自定义格式（思维导图/闪卡/LaTeX/typst/用户模板）
> 由 **Agent 把 MD 底稿当信息源自行生成**。这样 MCP 保持精简，输出格式无限扩展。

## 信息源：拿到底稿

任务成功后（`get_task_status` 返回 `SUCCESS`）：

1. **`get_task_files(task_id)`** —— 列出任务产物，找到 `{task_id}.json`（含 `markdown` 底稿 + `transcript`）。
2. 读 `{task_id}.json`：`result.markdown`（MD 底稿）、`result.transcript`（含 `full_text` 与 `segments` 时间轴）。
3. 便携笔记：`result.note_dir` 指向 `note.md` 所在目录。

底稿 = **转换的信息源**。所有格式转换都以它为依据，不再重新下载/转写。

## 机械格式（调 MCP 工具，不自己写）

`export_transcript(task_id, formats=["srt","vtt","json"], out_dir?)`

- 确定性渲染（时间轴换算），**不耗 LLM、不耗 token**，结果可离线核对。
- 返回 `{task_id, formats: {fmt: "file://绝对路径"}}`，直接 Read 即可用。
- 适用：字幕文件（SRT/VTT）、结构化转写（JSON）、给下游程序消费。
- 任务成功后若 setup 配置了「导出格式默认」，会自动导出这些格式——Agent 可直接读产物文件。

## 创意格式（Agent 基于底稿生成）

原则：读 `{task_id}.json` 的 `markdown` 底稿 → 按目标格式重写为对应文件 → 交付路径。

### 思维导图（Mermaid）
1. 读 MD 底稿，提炼层级大纲（标题 → 子要点 → 细节）。
2. 写 `mindmap.mmd`（Mermaid `mindmap` 语法），顶层为视频主题。
3. 可选：先给用户看大纲确认，再落文件。

### 闪卡（Anki/Q&A）
1. 从底稿抽取知识点 → 每张卡「问题 / 答案」。
2. 写 `flashcards.md`（`Q: …\nA: …` 格式），便于导入 Anki。

### LaTeX（模板驱动）
1. **列出 `templates/latex/` 里的风格让用户选**（默认 `academic`）：
   - `academic.tex` —— 学术/论文风
   - `lecture.tex` —— 讲义/课堂风
   - `meeting_minutes.tex` —— 会议纪要风
   - `minimal.tex` —— 极简风
2. **Read 所选模板 `.tex`**（含 frontmatter：`%% style: academic %%` 等，供确认）。
3. **以模板为风格骨架、底稿为信息源**，生成 `note.tex`：不直接替换 `%%CONTENT%%`
   占位符，而是按模板的文档类/章节结构/要点框习惯，把底稿内容**重构**进去。
4. 可选编译 PDF：若系统有 `xelatex`（`which xelatex`），可 `xelatex note.tex` 编译；
   没有则只交付 `.tex`。
5. **用户自定义模板**：用户提供 `.tex` 路径或放到 `templates/latex/`，同样处理。

### typst / 其他自定义模板
1. 读用户提供的模板文件（`.typ` / 其他格式）。
2. 把底稿内容填入模板结构 → 输出结果文件。

## 输出落盘位置

- 机械格式：`export_transcript` 写到 `note_results/{task_id}/`（`out_dir` 可覆盖），并记入 manifest（可被 `cleanup_note` 清理）。
- Agent 手写格式：写到 `note_dir`（若有）或当前工作目录，交付路径给用户。
