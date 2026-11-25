import re
import sys
import unittest
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from generate_profile import CalendarParser, group_sponsors, load_config, summarize

NS = {"svg": "http://www.w3.org/2000/svg"}


class CalendarTests(unittest.TestCase):
    def test_future_dates_and_formatted_counts(self):
        parser = CalendarParser()
        parser.feed('''<td id="a" data-date="2026-01-01" data-level="4"></td>
        <tool-tip for="a">1,234 contributions on January 1st.</tool-tip>
        <td id="b" data-date="2026-01-02" data-level="0"></td>
        <tool-tip for="b">No contributions on January 2nd.</tool-tip>''')
        self.assertEqual(parser.days(date(2026, 1, 1)), [{"date": "2026-01-01", "level": 4, "count": 1234}])

    def test_missing_tooltip_is_not_silently_zero(self):
        parser = CalendarParser()
        parser.feed('<td id="a" data-date="2026-01-01" data-level="0"></td>')
        with self.assertRaises(ValueError):
            parser.days(date(2026, 1, 1))

    def test_missing_calendar_date_is_rejected(self):
        parser = CalendarParser()
        parser.feed('<td id="a" data-date="2026-01-02" data-level="0"></td><tool-tip for="a">No contributions on January 2nd.</tool-tip>')
        with self.assertRaises(ValueError):
            parser.days(date(2026, 1, 2))

    def test_unfinished_day_preserves_yesterday_streak(self):
        days = [{"date": f"2026-01-{i:02d}", "count": n} for i, n in enumerate([1, 2, 0, 3, 4, 5, 0], 1)]
        summary = summarize(days)
        self.assertEqual((summary["currentStreak"], summary["longestStreak"]), (3, 3))
        self.assertEqual((summary["currentStart"], summary["currentEnd"]), ("2026-01-04", "2026-01-06"))
        self.assertEqual(summary["total"], 15)
        self.assertEqual(summarize(days + [{"date": "2026-01-08", "count": 0}])["currentStreak"], 0)


class SponsorTests(unittest.TestCase):
    SETTINGS = {"tiers": [{"from": 5, "name": "torii/"}, {"from": 25, "name": "edge-guardian/"}, {"from": 10, "name": "lantern/"}]}

    @staticmethod
    def node(login, amount, privacy="PUBLIC", created="2026-01-01"):
        return {"privacyLevel": privacy, "createdAt": created, "tier": {"monthlyPriceInDollars": amount}, "sponsorEntity": {"login": login}}

    def test_tiers_private_sponsors_and_friends(self):
        nodes = [self.node("late", 10, created="2026-03-01"), self.node("early", 10, created="2026-02-01"),
                 self.node("big", 40), self.node("exact", 5), self.node("small", 2), self.node("coffee", 1),
                 self.node("hidden", 100, privacy="PRIVATE"),
                 {"privacyLevel": "PUBLIC", "createdAt": "2026-01-01", "tier": None, "sponsorEntity": {"login": "custom"}},
                 {"privacyLevel": "PUBLIC", "createdAt": "2026-01-01", "tier": {"monthlyPriceInDollars": 50}, "sponsorEntity": {}}]
        result = group_sponsors(nodes, self.SETTINGS)
        self.assertEqual(result["sponsors"], [
            {"login": "big", "tier": "edge-guardian/"}, {"login": "exact", "tier": "torii/"},
            {"login": "early", "tier": "lantern/"}, {"login": "late", "tier": "lantern/"}])
        self.assertEqual(result["friends"], 3)  # small, coffee and the custom amount without a tier
        self.assertNotIn("hidden", str(result))

    def test_saved_data_never_contains_amounts(self):
        result = group_sponsors([self.node("big", 40)], self.SETTINGS)
        self.assertNotIn("40", str(result))


class ReadmeTests(unittest.TestCase):
    def test_picture_sources_keep_the_same_scale(self):
        # GitHub may pick either source for a signed-in theme, so both must fit the fallback size.
        for fragment in re.findall(r"<picture>.*?</picture>", (ROOT / "README.md").read_text(encoding="utf-8"), re.S):
            picture = ET.fromstring(re.sub(r"<(source|img)([^>]*?)/?>", lambda m: "<" + m[1] + m[2] + "/>", fragment))
            fallback = picture.find("img")
            base = ET.parse(ROOT / fallback.attrib["src"]).getroot()
            ratio = float(base.attrib["width"]) / float(base.attrib["height"])
            for source in picture.findall("source"):
                art = ET.parse(ROOT / source.attrib["srcset"]).getroot()
                with self.subTest(source=source.attrib["srcset"]):
                    self.assertAlmostEqual(float(art.attrib["width"]) / float(art.attrib["height"]), ratio)
                    if "width" in fallback.attrib:
                        self.assertGreaterEqual(float(art.attrib["width"]), float(fallback.attrib["width"]))

    def test_every_configured_badge_is_in_the_readme(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for item in load_config()["badges"]:
            for theme in ("light", "dark"):
                self.assertIn(f'assets/badge-{item["slug"]}-{theme}.svg', readme)


class ArtworkTests(unittest.TestCase):
    def test_generated_art_is_self_contained_vector_art(self):
        names = ["header", "workspace", "github", "sponsors"] + [f'badge-{item["slug"]}' for item in load_config()["badges"]]
        for name in names:
            for theme in ("light", "dark"):
                with self.subTest(asset=name, theme=theme):
                    art = ET.parse(ROOT / f"assets/{name}-{theme}.svg").getroot()
                    if not name.startswith("badge-"):
                        self.assertEqual(art.attrib["width"], "788")
                    for tag in ["text", "script", "foreignObject"]:
                        self.assertIsNone(art.find(f".//svg:{tag}", NS))
                    # GitHub never fetches external images from inside an SVG: photos must be embedded.
                    for image in art.findall(".//svg:image", NS):
                        self.assertRegex(image.attrib["href"], r"^data:image/(jpeg|png);base64,")
                    ids = {element.attrib["id"] for element in art.iter() if "id" in element.attrib}
                    for element in [*art.findall(".//svg:use", NS), *art.findall(".//svg:mpath", NS)]:
                        self.assertTrue(element.attrib["href"].startswith("#"))
                        self.assertIn(element.attrib["href"][1:], ids)
                    for attr in ["fill", "clip-path", "mask", "filter"]:
                        for element in art.iter():
                            ref = re.fullmatch(r"url\(#(.+)\)", element.attrib.get(attr, ""))
                            if ref:
                                self.assertIn(ref[1], ids)

    def test_both_themes_share_one_layout(self):
        for name in ["header", "workspace", "github", "sponsors"]:
            light, dark = (ET.parse(ROOT / f"assets/{name}-{theme}.svg").getroot() for theme in ("light", "dark"))
            self.assertEqual((light.attrib["width"], light.attrib["height"]), (dark.attrib["width"], dark.attrib["height"]))

    def test_github_card_has_one_train_of_seven_cars(self):
        for theme in ("light", "dark"):
            with self.subTest(theme=theme):
                art = ET.parse(ROOT / f"assets/github-{theme}.svg").getroot()
                self.assertEqual(len(art.findall(".//svg:animateMotion", NS)), 7)


class TrailAnimationTests(unittest.TestCase):
    def test_squares_dim_when_the_train_arrives_and_return_after_it_leaves(self):
        from artwork import draw_trail
        from canvas import Canvas

        first = date(2026, 1, 1)
        days = [dict(date=(first + timedelta(days=i)).isoformat(), count=int(i != 2), level=int(i != 2)) for i in range(14)]
        for theme in ("light", "dark"):
            with self.subTest(theme=theme):
                canvas = Canvas(theme, 412)
                draw_trail(canvas, {"days": days}, 71, 257, 752, 386, "footer")
                art = ET.fromstring(canvas.finish("trail"))
                train = art.find('svg:g[@class="trail"]', NS)
                self.assertIsNotNone(train)
                motions = train.findall("svg:rect/svg:animateMotion", NS)
                self.assertEqual(len(motions), 7)
                head = motions[-1]
                route_id = head.find("svg:mpath", NS).attrib["href"][1:]
                path = art.find(f'.//svg:path[@id="{route_id}"]', NS)
                points = [(int(x), int(y)) for x, y in re.findall(r"(-?\d+),(-?\d+)", path.attrib["d"])]
                self.assertTrue(all(abs(x - nx) + abs(y - ny) == 1 for (x, y), (nx, ny) in zip(points, points[1:])))
                _, head_start, head_end, _ = map(float, head.attrib["keyTimes"].split(";"))
                tail_end = head_end
                for motion in reversed(motions[:-1]):
                    _, start, end, _ = map(float, motion.attrib["keyTimes"].split(";"))
                    self.assertGreater(end, tail_end)
                    self.assertAlmostEqual(end - start, head_end - head_start, places=7)
                    tail_end = end

                tx, ty, step = map(float, re.findall(r"[\d.]+", train.attrib["transform"]))
                cells = art.findall('svg:rect[@class="contribution"]', NS)
                self.assertEqual(len(cells), len(days))
                for day, rect in zip(days, cells):
                    with self.subTest(day=day["date"]):
                        x, y, size = (float(rect.attrib[attr]) for attr in ("x", "y", "width"))
                        col, row = (x + size / 2 - tx) / step, (y + size / 2 - ty) / step
                        self.assertAlmostEqual(col, round(col), places=3)
                        self.assertAlmostEqual(row, round(row), places=3)
                        progress = points.index((round(col), round(row))) / (len(points) - 1)
                        anim = rect.find('svg:animate[@attributeName="opacity"]', NS)
                        if not day["count"]:
                            self.assertIsNone(anim)
                            continue
                        arrive = head_start + progress * (head_end - head_start)
                        _, dim, dimmed, restore, restored, _ = map(float, anim.attrib["keyTimes"].split(";"))
                        self.assertAlmostEqual(dim, arrive, places=7)
                        self.assertLess(dim, dimmed)
                        self.assertLess(dimmed, restore)
                        self.assertGreaterEqual(restore, tail_end)
                        self.assertLess(restore, restored)
                        self.assertLess(restored, 1)
                        for attr in ("dur", "repeatCount", "begin"):
                            self.assertEqual(anim.get(attr), head.get(attr))


if __name__ == "__main__":
    unittest.main()
