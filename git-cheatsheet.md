# Git 速查表（Cheat Sheet）

## 一、首次配置

```bash
git config --global user.name  "你的名字"
git config --global user.email "you@example.com"
git config --global init.defaultBranch main
git config --global core.autocrlf true      # Windows 建议；macOS/Linux 用 input 或 false
git config --global core.editor "code --wait"   # 可选：用 VS Code 写提交信息

git config --list --show-origin            # 查看当前所有配置来自哪个文件
```

## 二、创建 / 获取仓库

```bash
git init                    # 把当前目录变成 Git 仓库
git clone <url>             # 克隆远程仓库
git clone <url> myfolder    # 克隆到指定目录名
```

## 三、日常闭环（最重要）

```bash
git status                  # 看现在处于什么状态（最常用，迷路就敲它）
git diff                    # 看还没暂存的改动
git diff --staged           # 看已暂存、即将提交的改动
git add <文件>              # 暂存某个文件
git add .                   # 暂存当前目录全部改动
git add -p                  # 逐块挑选要暂存的改动（强烈推荐）
git commit -m "说明"        # 提交
git commit -am "说明"       # 跳过 add，提交「已跟踪」文件的改动（不含新文件）
git log --oneline --graph --all   # 图形化看历史
```

## 四、分支

```bash
git branch                  # 列出本地分支
git branch -a               # 含远程分支
git switch -c feature/x     # 新建并切换到 feature/x
git switch main             # 切换分支
git merge feature/x         # 把 feature/x 合并进当前分支
git branch -d feature/x     # 删除已合并的分支
git branch -D feature/x     # 强制删除
```

## 五、远程协作

```bash
git remote -v                          # 查看远程地址
git remote add origin <url>            # 关联远程
git push -u origin main                # 首次推送并建立跟踪关系
git push                               # 之后直接推
git fetch                              # 只下载远程更新，不动工作区
git pull                               # fetch + merge
git pull --rebase                      # fetch + rebase（历史更干净）
```

## 六、后悔药

| 场景 | 命令 |
| --- | --- |
| 改了文件想还原（未 add） | `git restore <文件>` |
| 已 add，想取消暂存 | `git restore --staged <文件>` |
| 刚提交，想改信息或补文件 | `git add <漏的文件>` → `git commit --amend` |
| 撤销某个「已推送」的提交 | `git revert <commit>`（生成反向提交，安全） |
| 本地未推送，想彻底回退 | `git reset --hard <commit>`（**会丢改动**） |
| 临时收起手头改动 | `git stash` / `git stash pop` |
| 误删分支 / 误 reset | `git reflog` 找到旧 HEAD，再 `git reset --hard <hash>` |
| 清理未跟踪文件 | `git clean -n` 先预览，再 `git clean -fd`（**会删文件**） |

## 七、.gitignore 示例

```gitignore
node_modules/
dist/
build/
*.log
.env
.DS_Store
Thumbs.db
.idea/
.vscode/
```

规则：`/` 结尾表示目录，`*` 通配，`!` 取反。已被跟踪的文件不会因加入 ignore 而失效，需 `git rm --cached <文件>`。

## 八、冲突处理三步

```bash
git status                 # 1. 找出冲突文件（Unmerged paths）
# 2. 打开文件，删掉 <<<<<<< ======= >>>>>>> 标记，保留想要的内容
git add <冲突文件>          # 3. 标记已解决
git commit                 #    完成合并提交
```

放弃这次合并：`git merge --abort`。

## 九、提交信息规范（推荐 Conventional Commits）

```
feat: 新增导出 CSV 功能
fix: 修复登录页空指针
docs: 补充 README 安装说明
refactor: 抽离重复的请求逻辑
test: 补充订单模块单测
chore: 升级依赖
```

## 十、高频组合场景

```bash
# 推送前先同步
git fetch && git rebase origin/main

# 临时切换去修 bug
git stash push -m "wip"
git switch -c hotfix/login
# ... 修完提交、合并 ...
git switch - && git stash pop

# 看某行代码是谁改的、哪次提交
git blame <文件>
git log -p <文件>
git show <commit>
```
