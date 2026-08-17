#!/usr/bin/env bash
# 创建小样本沙盒，用于模板/样式快速本地验证。
#
# 背景：本机 2C/3.4G 无 swap，10k 页全量构建 RSS 1.3G+ 曾 3 次触发 OOM-kill
# （2026-08-18 事故，见 plan.md §12）。沙盒仅抽样数十篇，hugo server 秒级启动。
#
# 原理：不复制主仓库。server 在主仓库根运行（真实监听 layouts/assets/themes 改动），
# 通过 --config 叠加 override.toml 把 contentDir 指向沙盒目录。
#
# 用法:
#   scripts/mksandbox.sh [沙盒目录]        # 默认 /tmp/opencode/sandbox，样本数可用 N=50 覆盖
#   cd <项目根> && hugo server --port 1414 --config hugo.toml,<沙盒>/override.toml
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SB="${1:-/tmp/opencode/sandbox}"
POSTS="$ROOT/content/posts"
N="${N:-40}"

rm -rf "$SB"
mkdir -p "$SB/content/posts" "$SB/content/page/archives" "$SB/content/page/search" \
         "$SB/content/categories/coser"

# 固定页面（归档/搜索/模特墙入口）
cp "$ROOT/content/page/archives/index.md" "$SB/content/page/archives/"
cp "$ROOT/content/page/search/index.md"   "$SB/content/page/search/"
cp "$ROOT/content/categories/coser/_index.md" "$SB/content/categories/coser/"

# 抽样：固定边界样本 + 跨年份分布 + 头部若干篇
{
    echo "coser-w-171.md"                                    # 常规篇
    grep -l "\[Fantia\]" "$POSTS"/*.md 2>/dev/null | head -2 | xargs -r -n1 basename
    grep -l "鹿野希" "$POSTS"/*.md 2>/dev/null  | head -1 | xargs -r -n1 basename   # 括号别名
    grep -L "^models:" "$POSTS"/*.md 2>/dev/null | head -1 | xargs -r -n1 basename # 空 models
    for y in 2021 2022 2023 2024 2025 2026; do
        grep -l "^date: \"$y" "$POSTS"/*.md 2>/dev/null | head -5 | xargs -r -n1 basename
    done
    ls "$POSTS" | head -10
} | sort -u | head -n "$N" > "$SB/selected.txt" || true   # head 提前关管道会触发 SIGPIPE，勿因 pipefail 中断

while read -r f; do
    [ -n "$f" ] && cp "$POSTS/$f" "$SB/content/posts/"
done < "$SB/selected.txt"

cat > "$SB/override.toml" <<EOF
# 沙盒覆盖：仅替换 contentDir，其余配置沿用主仓库 hugo.toml
contentDir = "$SB/content"
EOF

cat <<EOF
沙盒就绪: $SB
  样本文章: $(ls "$SB/content/posts" | wc -l) 篇（跨 2021-2026 + 边界样本）
  启动命令:
    cd $ROOT
    hugo server --port 1414 --config hugo.toml,$SB/override.toml
  验证页面: /  /archives/  /categories/coser/  /tags/蝉时w/
  说明: layouts/assets/themes 为主仓库真实文件，改动即时热重载；
        全量验证交给 CI（Actions 2C/16G 构建后部署）
EOF
