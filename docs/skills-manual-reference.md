# Skills 手动触发参考手册

> 本文档列出**不会自动触发**的 Skills，按大类分组。自动触发的 Skills（如 `brainstorming`、`systematic-debugging`、`code-review`、`security-review` 等）不在本文档范围内。
>
> 触发方式说明：
> - **`/` 命令**：在对话中直接输入斜杠命令
> - **口头请求**：用自然语言描述需求，AI 自动匹配对应 Skill
> - **管道串联**：作为多步骤工作流的一环被调用

---

## 一、代码审查与质量（语言特定）

> 通用 `code-review` 是自动触发的；以下语言特定审查需**口头请求**或 **`/` 命令**。

| Skill | 触发方式 | 作用 |
|-------|----------|------|
| `cpp-review` | `/cpp-review` / 口头请求 | C++ 代码审查（内存安全、现代 C++、并发） |
| `flutter-review` | `/flutter-review` / 口头请求 | Flutter/Dart 代码审查（Widget 最佳实践、状态管理） |
| `go-review` | `/go-review` / 口头请求 | Go 代码审查（惯用写法、并发模式、错误处理） |
| `rust-review` | `/rust-review` / 口头请求 | Rust 代码审查（所有权、生命周期、unsafe） |
| `kotlin-review` | `/kotlin-review` / 口头请求 | Kotlin/Android 代码审查（协程、Compose） |
| `python-review` | `/python-review` / 口头请求 | Python 代码审查（PEP 8、类型提示、安全） |
| `fastapi-review` | `/fastapi-review` / 口头请求 | FastAPI 专项审查（异步、依赖注入、Pydantic） |
| `review` | `/review` / 口头请求 | 通用代码审查（不限定语言） |
| `simplify` | `/simplify` / 口头请求 | 审查 diff 并自动应用修复建议 |

---

## 二、构建与编译修复

> `build-error-resolver` agent 会在构建失败时自动介入；以下 Skills 用于**手动指定特定语言**的构建。

| Skill | 触发方式 | 作用 |
|-------|----------|------|
| `build-fix` | `/build-fix` / 口头请求 | 通用构建错误修复 |
| `cpp-build` | `/cpp-build` / 口头请求 | C++ 构建（CMake、编译、链接错误） |
| `flutter-build` | `/flutter-build` / 口头请求 | Flutter 构建（Dart 分析、编译错误） |
| `go-build` | `/go-build` / 口头请求 | Go 构建（vet、编译错误） |
| `rust-build` | `/rust-build` / 口头请求 | Rust 构建（cargo build、borrow checker） |
| `kotlin-build` | `/kotlin-build` / 口头请求 | Kotlin/Gradle 构建修复 |
| `gradle-build` | `/gradle-build` / 口头请求 | Gradle 构建系统专项修复 |

---

## 三、测试（语言特定）

> `tdd-guide` agent 会在新功能/bug 修复时自动介入；以下用于**手动运行特定语言测试**。

| Skill | 触发方式 | 作用 |
|-------|----------|------|
| `cpp-test` | `/cpp-test` / 口头请求 | C++ 测试运行与管理 |
| `flutter-test` | `/flutter-test` / 口头请求 | Flutter/Dart 测试运行 |
| `go-test` | `/go-test` / 口头请求 | Go 测试运行 |
| `rust-test` | `/rust-test` / 口头请求 | Rust 测试运行 |
| `kotlin-test` | `/kotlin-test` / 口头请求 | Kotlin 测试运行 |
| `test-coverage` | `/test-coverage` / 口头请求 | 分析测试覆盖率报告 |
| `playwright-skill:playwright-skill` | 口头请求 | Playwright E2E 浏览器测试 |

---

## 四、项目管理与 PR

| Skill | 触发方式 | 作用 |
|-------|----------|------|
| `project-init` | `/project-init` / 口头请求 | 初始化新项目结构 |
| `projects` | `/projects` / 口头请求 | 多项目管理与切换 |
| `init` | `/init` / 口头请求 | 在当前目录初始化项目 |
| `pr` | `/pr` / 口头请求 | 创建 Pull Request（自动分析提交历史） |
| `review-pr` | `/review-pr` / 口头请求 | 审查指定 PR（传入 PR 号或 URL） |
| `promote` | `/promote` / 口头请求 | 提升/发布分支到正式环境 |
| `jira` | `/jira` / 口头请求 | Jira 工单操作 |
| `feature-dev` | `/feature-dev` / 口头请求 | 完整功能开发流程（研究→规划→实现→审查） |

### PR 流程子步骤（可单独调用）

| Skill | 触发方式 | 作用 |
|-------|----------|------|
| `prp-plan` | `/prp-plan` | PR 流程：规划阶段 |
| `prp-prd` | `/prp-prd` | PR 流程：编写 PRD |
| `prp-implement` | `/prp-implement` | PR 流程：实现阶段 |
| `prp-commit` | `/prp-commit` | PR 流程：提交阶段 |
| `prp-pr` | `/prp-pr` | PR 流程：创建 PR |

---

## 五、会话与工作流管理

| Skill | 触发方式 | 作用 |
|-------|----------|------|
| `checkpoint` | `/checkpoint` / 口头请求 | 创建会话检查点（可回退） |
| `save-session` | `/save-session` / 口头请求 | 保存当前会话状态 |
| `resume-session` | `/resume-session` / 口头请求 | 恢复之前的会话 |
| `sessions` | `/sessions` / 口头请求 | 列出所有已保存会话 |
| `aside` | `/aside` / 口头请求 | 暂存当前工作，开启临时分支任务 |
| `loop` | `/loop` / 口头请求 | 定时循环执行指定命令（如 `/loop 5m /test`） |
| `loop-start` | `/loop-start` / 口头请求 | 启动自主循环任务 |
| `loop-status` | `/loop-status` / 口头请求 | 查看循环任务状态 |
| `santa-loop` | `/santa-loop` / 口头请求 | Santa 循环模式 |
| `evolve` | `/evolve` / 口头请求 | 演进式改进当前代码 |

---

## 六、规划与设计

> `superpowers:brainstorming` 是自动触发的；以下需**手动调用**。

| Skill | 触发方式 | 作用 |
|-------|----------|------|
| `plan` | `/plan` / 口头请求 | 需求陈述 → 风险评估 → 分步实现计划（需用户确认后才编码） |
| `plan-prd` | `/plan-prd` / 口头请求 | 编写产品需求文档（PRD） |
| `gan-design` | `/gan-design` / 口头请求 | GAN 模式：设计阶段 |
| `gan-build` | `/gan-build` / 口头请求 | GAN 模式：构建阶段 |

---

## 七、Multi- 系列（多目标并行）

| Skill | 触发方式 | 作用 |
|-------|----------|------|
| `multi-backend` | `/multi-backend` / 口头请求 | 并行处理多个后端任务 |
| `multi-frontend` | `/multi-frontend` / 口头请求 | 并行处理多个前端任务 |
| `multi-execute` | `/multi-execute` / 口头请求 | 并行执行多个独立任务 |
| `multi-plan` | `/multi-plan` / 口头请求 | 并行规划多个功能 |
| `multi-workflow` | `/multi-workflow` / 口头请求 | 并行运行多个工作流 |

---

## 八、文档与内容生成（document-skills）

> 全部需**口头请求**触发，部分支持 **`/` 命令**。

| Skill | 触发方式 | 作用 |
|-------|----------|------|
| `document-skills:frontend-design` | 口头请求 | 前端 UI 设计与组件生成 |
| `document-skills:mcp-builder` | 口头请求 | 构建 MCP (Model Context Protocol) 服务器 |
| `document-skills:claude-api` | 口头请求 | Claude API / Anthropic SDK 应用开发 |
| `document-skills:web-artifacts-builder` | 口头请求 | 构建复杂 Web 交互构件 |
| `document-skills:skill-creator` | 口头请求 | 创建自定义 Skill |
| `document-skills:pptx` | 口头请求 | 生成 PowerPoint 演示文稿 |
| `document-skills:docx` | 口头请求 | 生成 Word 文档 |
| `document-skills:pdf` | 口头请求 | 生成 PDF 文档 |
| `document-skills:xlsx` | 口头请求 | 生成 Excel 电子表格 |
| `document-skills:canvas-design` | 口头请求 | Canvas 图形设计 |
| `document-skills:algorithmic-art` | 口头请求 | 算法艺术生成（p5.js） |
| `document-skills:theme-factory` | 口头请求 | 主题/配色方案工厂 |
| `document-skills:brand-guidelines` | 口头请求 | 品牌指南设计 |
| `document-skills:doc-coauthoring` | 口头请求 | 文档协作撰写 |
| `document-skills:internal-comms` | 口头请求 | 内部通讯文档撰写 |
| `document-skills:webapp-testing` | 口头请求 | Web 应用测试（Playwright） |
| `document-skills:slack-gif-creator` | 口头请求 | 创建 Slack GIF 动图 |

---

## 九、配置与工具

| Skill | 触发方式 | 作用 |
|-------|----------|------|
| `update-config` | `/update-config` / 口头请求 | 配置 Claude Code 设置（settings.json、权限、环境变量） |
| `keybindings-help` | `/keybindings-help` / 口头请求 | 自定义键盘快捷键 |
| `fewer-permission-prompts` | `/fewer-permission-prompts` / 口头请求 | 分析调用历史，减少权限弹窗 |
| `update-codemaps` | `/update-codemaps` / 口头请求 | 更新代码地图（CODEMAPS） |
| `update-docs` | `/update-docs` / 口头请求 | 更新项目文档 |
| `skill-create` | `/skill-create` / 口头请求 | 创建新的自定义 Skill |
| `skill-health` | `/skill-health` / 口头请求 | 检查已安装 Skill 的健康状态 |

---

## 十、运行与验证

| Skill | 触发方式 | 作用 |
|-------|----------|------|
| `run` | `/run` / 口头请求 | 启动并运行项目应用，验证变更效果 |
| `verify` | `/verify` / 口头请求 | 验证代码变更是否达到预期效果（手动测试） |
| `pm2` | `/pm2` / 口头请求 | PM2 进程管理操作 |

---

## 十一、监控与分析

| Skill | 触发方式 | 作用 |
|-------|----------|------|
| `cost-report` | `/cost-report` / 口头请求 | 生成 API 使用成本报告 |
| `model-route` | `/model-route` / 口头请求 | 模型路由选择与管理 |
| `quality-gate` | `/quality-gate` / 口头请求 | 质量门检查（合并前全面审查） |
| `harness-audit` | `/harness-audit` / 口头请求 | 分析 Agent Harness 配置的可靠性与效率 |

---

## 十二、Hookify 系列

| Skill | 触发方式 | 作用 |
|-------|----------|------|
| `hookify` | `/hookify` / 口头请求 | 从对话中自动提取 Hook 配置 |
| `hookify-configure` | `/hookify-configure` / 口头请求 | 配置 Hookify 参数 |
| `hookify-help` | `/hookify-help` / 口头请求 | Hookify 使用帮助 |
| `hookify-list` | `/hookify-list` / 口头请求 | 列出当前所有 Hook |

---

## 十三、Instinct 系列（学习与导出）

| Skill | 触发方式 | 作用 |
|-------|----------|------|
| `instinct-export` | `/instinct-export` / 口头请求 | 导出会话中的经验教训 |
| `instinct-import` | `/instinct-import` / 口头请求 | 导入之前的经验教训 |
| `instinct-status` | `/instinct-status` / 口头请求 | 查看 Instinct 状态 |
| `learn` | `/learn` / 口头请求 | 从当前会话学习并记录 |
| `learn-eval` | `/learn-eval` / 口头请求 | 评估学习效果 |

---

## 十四、维护与清理

| Skill | 触发方式 | 作用 |
|-------|----------|------|
| `prune` | `/prune` / 口头请求 | 清理无用文件和依赖 |
| `refactor-clean` | `/refactor-clean` / 口头请求 | 死代码检测与安全移除 |

---

## 十五、其他

| Skill | 触发方式 | 作用 |
|-------|----------|------|
| `ecc-guide` | `/ecc-guide` / 口头请求 | ECC（Everything Claude Code）使用指南 |

---

## 快速索引

### 按触发方式汇总

| 触发方式 | Skills |
|----------|--------|
| **`/` 命令**（显式输入斜杠） | 全部支持，推荐 `checkpoint`、`pr`、`save-session`、`loop`、`aside` 等高频操作 |
| **口头请求**（自然语言） | 全部支持，AI 自动匹配最合适的 Skill |
| **管道串联**（工作流内调用） | `prp-*`、`multi-*`、`gan-*`、`hookify-*` 系列 |

### 按使用频率推荐

| 频率 | Skills |
|------|--------|
| **高频**（日常使用） | `pr`、`review-pr`、`checkpoint`、`save-session`、`verify`、`run` |
| **中频**（按需使用） | `plan`、`test-coverage`、`simplify`、`update-config`、`fewer-permission-prompts` |
| **低频**（特定场景） | 语言特定 build/review/test、`document-skills:*`、`multi-*`、`gan-*` |
