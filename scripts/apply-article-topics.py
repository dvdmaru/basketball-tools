#!/usr/bin/env python3
"""把已核定的 slug → topic 對照寫進文章 frontmatter，不觸碰正文。"""
import json
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
ARTICLES = ROOT / "articles"


def update_article(path: pathlib.Path, mapping: dict) -> bool:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"缺少 frontmatter：{path}")
    end = text.find("\n---", 4)
    if end < 0:
        raise ValueError(f"frontmatter 未關閉：{path}")

    frontmatter = text[4:end]
    body = text[end:]
    slug = path.parent.name
    entry = mapping.get(slug)
    if entry is None:
        raise ValueError(f"主題表缺少 slug：{slug}")

    lines = frontmatter.splitlines(keepends=True)
    if any(line.startswith("topic:") or line.startswith("topic2:") for line in lines):
        raise ValueError(f"已有 topic 欄位，拒絕覆寫：{path}")

    inserted = False
    output = []
    for line in lines:
        if line == 'competition: "nba"\n':
            line = "competition: nba\n"
        output.append(line)
        if line.startswith("competition:"):
            output.append(f"topic: {entry['topic']}\n")
            if entry.get("topic2"):
                output.append(f"topic2: {entry['topic2']}\n")
            inserted = True
    if not inserted:
        raise ValueError(f"缺少 competition 欄位：{path}")

    updated = "---\n" + "".join(output) + body
    if updated != text:
        path.write_text(updated, encoding="utf-8")
        return True
    return False


def main() -> int:
    if len(sys.argv) != 2:
        print("用法：python3 scripts/apply-article-topics.py <topic-map.json>", file=sys.stderr)
        return 2
    mapping = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
    paths = sorted(ARTICLES.glob("*/index.md"))
    if set(mapping) != {path.parent.name for path in paths}:
        raise ValueError("topic map 與 articles slug 集合不一致")
    changed = sum(update_article(path, mapping) for path in paths)
    print(f"已更新 {changed} 篇文章 frontmatter")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
