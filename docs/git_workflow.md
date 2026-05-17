# Git 版本管理与团队协作指南

这份文档用于三人协作开发本项目。目标是：每个人都能安全使用 AI coding 开发自己的部分，减少代码冲突，保证 `main` 分支始终可运行。

## 核心原则

1. `main` 分支只放稳定代码。
2. 每个人做功能都从 `main` 新建自己的分支。
3. 每次提交前先确认改动范围，不要把别人负责的文件一起提交。
4. 合并前必须能通过基础验证。
5. 不提交 `.env`、`.venv`、`node_modules`、`dist`、`__pycache__`。
6. AI coding 生成代码后，自己必须 review 一遍再提交。

## 仓库地址

```text
https://github.com/key641/Three-of-Spades
```

首次拉取：

```bash
git clone https://github.com/key641/Three-of-Spades.git
cd Three-of-Spades
```

## 分支命名规范

建议按负责人和任务命名：

```text
feature/a-agent-intent
feature/a-llm-provider
feature/b-poi-search
feature/b-route-scoring
feature/c-route-card-ui
feature/c-replan-panel
fix/chat-api-error
docs/update-readme
```

规则：

- A 同学功能分支以 `feature/a-` 开头。
- B 同学功能分支以 `feature/b-` 开头。
- C 同学功能分支以 `feature/c-` 开头。
- 修 bug 用 `fix/`。
- 改文档用 `docs/`。

## 每天开始开发前

先切回 `main` 并拉最新代码：

```bash
git switch main
git pull origin main
```

然后新建当天任务分支：

```bash
git switch -c feature/a-agent-intent
```

如果已经有分支，切回自己的分支后同步 `main`：

```bash
git switch feature/a-agent-intent
git fetch origin
git merge origin/main
```

## 每次提交前检查

查看自己改了什么：

```bash
git status
git diff
```

如果只想看文件列表：

```bash
git status --short
```

确认不要提交这些内容：

```text
.env
backend/.venv/
frontend/node_modules/
frontend/dist/
__pycache__/
*.pyc
*.log
*.db
```

这些已经在 `.gitignore` 中忽略，但提交前仍然要看一眼。

## 提交规范

提交信息建议格式：

```text
type(scope): summary
```

常用 type：

| type | 用途 |
| --- | --- |
| `feat` | 新功能 |
| `fix` | 修 bug |
| `docs` | 文档 |
| `refactor` | 重构，不改变行为 |
| `test` | 测试 |
| `chore` | 工程配置、依赖等 |

示例：

```bash
git add backend/app/services/poi_service.py data/seed/pois.json
git commit -m "feat(route): add poi search scoring"
```

不要使用过于模糊的提交信息：

```text
update
fix
改了一下
final version
```

## 每个人推荐的提交范围

### A 同学

主要提交：

```text
backend/app/api/chat.py
backend/app/agent/
backend/app/llm/
backend/app/services/profile_service.py
backend/app/tools/intent_tool.py
backend/app/tools/profile_tool.py
backend/app/tools/feedback_tool.py
backend/app/schemas/intent.py
backend/app/schemas/chat.py
```

提交前验证：

```bash
cd backend
.\.venv\Scripts\python.exe -m compileall app
```

### B 同学

主要提交：

```text
backend/app/services/poi_service.py
backend/app/services/route_service.py
backend/app/services/scoring_service.py
backend/app/services/replan_service.py
backend/app/tools/poi_tool.py
backend/app/tools/route_tool.py
backend/app/tools/replan_tool.py
backend/app/schemas/poi.py
backend/app/schemas/route.py
data/seed/
```

提交前验证：

```bash
cd backend
.\.venv\Scripts\python.exe -m compileall app
```

### C 同学

主要提交：

```text
frontend/src/pages/
frontend/src/components/
frontend/src/hooks/
frontend/src/styles/
frontend/src/api/
```

提交前验证：

```bash
cd frontend
npm run build
```

## 接口字段变更流程

如果要改 `Intent`、`POI`、`Route`、`ChatResponse` 等接口字段，必须按这个顺序：

```text
1. 在群里说明字段变更
2. 改 backend/app/schemas/
3. 改 frontend/src/api/types.ts
4. 改 docs/api_contract.md
5. 跑后端 compileall
6. 跑前端 npm run build
7. 再提交
```

字段变更提交信息示例：

```bash
git commit -m "feat(contract): add route walking minutes"
```

## 推送分支

开发完成并提交后，推送自己的分支：

```bash
git push -u origin feature/a-agent-intent
```

如果之后继续在同一个分支提交：

```bash
git push
```

## 合并到 main

推荐流程：

```text
1. 自己分支提交完成
2. 推送到 GitHub
3. 开 Pull Request
4. 至少另一个人看一眼
5. 确认能跑后合并
```

如果时间紧，也可以线下确认后由一人合并，但合并前必须跑：

```bash
cd backend
.\.venv\Scripts\python.exe -m compileall app
```

```bash
cd frontend
npm run build
```

## 处理冲突

冲突最常见位置：

```text
README.md
docs/api_contract.md
backend/app/schemas/route.py
frontend/src/api/types.ts
frontend/src/components/RouteCard.tsx
```

遇到冲突时：

1. 不要让 AI 直接“随便解决所有冲突”。
2. 先看冲突文件是谁负责的。
3. 如果是接口字段冲突，A/B/C 一起确认字段。
4. 保留两边真正需要的逻辑，不要简单删除另一方代码。
5. 解决后必须跑验证。

查看冲突：

```bash
git status
```

解决后：

```bash
git add <resolved-files>
git commit
```

## 回退错误改动

如果还没提交，只想丢弃某个文件的改动：

```bash
git restore <file>
```

如果已经提交但还没推送，可以新提交修复，不建议初学阶段频繁改历史。

如果已经推送到远程，优先用新 commit 修复，不要强推：

```bash
git commit -m "fix(scope): correct previous change"
git push
```

除非三个人都确认，否则不要使用：

```bash
git push --force
git reset --hard
```

## AI coding 特别注意

使用 AI coding 前，在 prompt 里明确：

```text
当前分支：
负责模块：
允许修改的文件：
不要修改的文件：
验收命令：
```

AI 改完后先看：

```bash
git diff
```

确认没有改到别人文件，再提交。

## 推荐节奏

```text
Day 1-5：小步提交，优先端到端跑通
Day 6-14：每个功能单独分支，合并前跑验证
Day 15-17：减少接口变更，只修核心功能
Day 18-21：冻结 main，只做 bugfix 和演示打磨
```

第 3 周后半不要再大改数据结构和接口字段。

