#!/usr/bin/env python3
"""Compile v2 specs, lint the original scenes, and write before/after images.

Box-local runner. Do not copy absolute paths into the plugin.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from compile import compile_spec, lint_legacy
from hud import contact_sheet, side_by_side
from renderlib import render_compiled

SPEC_DIR = HERE / "specs"
OUT = HERE / "out"
LEGACY = Path("legacy-scenes")  # BOX-LOCAL fake-games dir; do not copy


def dump(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    legacy_reports = {}
    for name in ("ciderlatch", "heliox-yard", "gloamhollow", "gablewalk"):
        src = LEGACY / f"{name}.json"
        if not src.is_file():
            continue
        report = lint_legacy(json.loads(src.read_text()))
        legacy_reports[name] = report
        dump(OUT / f"{name}-legacy-lint.json", report)
        print(f"legacy lint {name}: overlaps={report.get('overlap_pairs')} "
              f"char_overlaps={report.get('character_overlaps')} "
              f"vfx={report.get('vfx')} wall_cover={report.get('wall_as_cover')} "
              f"issues={len(report['issues'])}")

    pairs = []
    for spec_name, title in (("ciderlatch", "Ciderlatch"), ("heliox-yard", "Heliox Yard")):
        spec = json.loads((SPEC_DIR / f"{spec_name}.json").read_text())
        compiled = compile_spec(spec)
        dump(OUT / f"{spec_name}.json", {
            "id": compiled["id"],
            "width": compiled["width"],
            "height": compiled["height"],
            "background": compiled["background"],
            "layers": compiled["layers"],
            "layer_count": compiled["layer_count"],
            "meta": compiled["meta"],
            "hud": compiled["hud"],
            "placements": compiled["placements"],
            "issues": compiled["issues"],
            "ok": compiled["ok"],
        })
        dump(OUT / f"{spec_name}-lint.json", {"id": compiled["id"], "ok": compiled["ok"], "issues": compiled["issues"]})
        print(f"compiled {spec_name}: layers={compiled['layer_count']} ok={compiled['ok']} "
              f"issues={len(compiled['issues'])}")
        for iss in compiled["issues"]:
            print(f"  {iss['severity']} {iss['code']}: {iss['message']}")
        png = OUT / f"{spec_name}.png"
        info = render_compiled(compiled, png)
        print(f"  wrote {info['png']} {info['size']}")
        before = LEGACY / f"{spec_name}.png"
        after = png
        sheet = OUT / f"{spec_name}-before-after.jpg"
        side_by_side(before, after, sheet, title=title)
        print(f"  wrote {sheet}")
        pairs.append((title, before, after))

    contact = OUT / "comparison-sheet.jpg"
    contact_sheet(pairs, contact)
    print(f"wrote {contact}")
    dump(OUT / "legacy-lint-all.json", legacy_reports)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
