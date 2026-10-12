#!/usr/bin/env python3
"""文章主題、延伸閱讀與分組索引的建置期回歸保護。"""
import collections
import importlib.util
import json
import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("build_articles", ROOT / "scripts" / "build-articles.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ba = _load()


class TestArticleTopics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.topic_config = json.loads((ROOT / "config" / "article-topics.json").read_text(encoding="utf-8"))
        cls.topics = cls.topic_config["topics"]
        cls.topic_keys = [topic["key"] for topic in cls.topics]
        cls.article_paths = sorted((ROOT / "articles").glob("*/index.md"))
        cls.articles = []
        for path in cls.article_paths:
            meta, _body = ba.parse_frontmatter(path.read_text(encoding="utf-8"))
            cls.articles.append({"slug": path.parent.name, "meta": meta})
        # The assertions below inspect the generated site, not a stale checked-in artifact.
        ba.build()

    def test_all_articles_have_registered_topics(self):
        self.assertEqual(len(self.articles), 86)
        self.assertEqual(len(self.topic_keys), 9)
        self.assertEqual(self.topic_keys, [topic["key"] for topic in ba.ARTICLE_TOPICS])
        for article in self.articles:
            meta = article["meta"]
            self.assertIn(meta.get("topic"), self.topic_keys, article["slug"])
            if meta.get("topic2"):
                self.assertIn(meta["topic2"], self.topic_keys, article["slug"])

    def test_generated_related_reading_is_internal_and_excludes_self(self):
        section_re = re.compile(r'<section class="related-reading".*?</section>', re.S)
        href_re = re.compile(r'href="/articles/([^/]+)/"')
        for article in self.articles:
            page = ROOT / "public-basketball" / "articles" / article["slug"] / "index.html"
            html = page.read_text(encoding="utf-8")
            match = section_re.search(html)
            self.assertIsNotNone(match, article["slug"])
            targets = href_re.findall(match.group(0))
            self.assertGreaterEqual(len(targets), 3, article["slug"])
            self.assertLessEqual(len(targets), 4, article["slug"])
            self.assertEqual(len(targets), len(set(targets)), article["slug"])
            self.assertNotIn(article["slug"], targets, article["slug"])
            for target in targets:
                self.assertTrue((ROOT / "public-basketball" / "articles" / target / "index.html").exists(),
                                f"{article['slug']} → {target}")

    def test_index_groups_each_article_once_in_configured_order(self):
        html = (ROOT / "public-basketball" / "articles" / "index.html").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r'<h2 id="([^"]+)">', html), self.topic_keys)
        targets = re.findall(r'href="/articles/([^/]+)/"', html)
        counts = collections.Counter(targets)
        article_slugs = {article["slug"] for article in self.articles}
        self.assertEqual(set(counts), article_slugs)
        self.assertTrue(all(counts[slug] == 1 for slug in article_slugs), counts)
        for topic in self.topics:
            self.assertIn(f'href="#{topic["key"]}"', html)


if __name__ == "__main__":
    unittest.main()
