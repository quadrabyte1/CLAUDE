#!/usr/bin/env python3
"""Throw-away parser for the IWI Enterprise Database Schema drawio (v1.0).

Extracts entities (swimlane vertices with child column vertices) and
edges (relationships) plus edgeLabel children (verb/multiplicity).
Emits a human-readable dump to stdout for Reed to eyeball before writing SQL.
"""

import html
import re
import xml.etree.ElementTree as ET
from collections import defaultdict

DRAWIO = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/ItWentIn/IWI Enterprise Database Schema.drawio"

tree = ET.parse(DRAWIO)
root = tree.getroot()

# Locate <root> inside mxGraphModel
mxroot = root.find(".//root")
cells = list(mxroot.findall("mxCell"))

# Index by id
by_id = {c.attrib["id"]: c for c in cells}

# Find swimlane entity vertices (style contains "swimlane" and value is the table name)
entities = {}       # id -> {"name": str, "parent_group": str, "columns": [id...]}
columns_by_parent = defaultdict(list)

# The "group" cells (parent="0" with a plain value) are subject-area groupings
groups = {c.attrib["id"]: c.attrib.get("value", "")
          for c in cells
          if c.attrib.get("parent") == "0" and c.attrib.get("value")}

for c in cells:
    style = c.attrib.get("style", "") or ""
    if c.attrib.get("vertex") == "1" and "swimlane" in style:
        entities[c.attrib["id"]] = {
            "name": c.attrib.get("value", "").strip(),
            "parent_group": groups.get(c.attrib.get("parent", ""), ""),
            "columns": [],
        }

# Column rows are vertex cells whose parent is a swimlane entity
for c in cells:
    p = c.attrib.get("parent", "")
    if p in entities and c.attrib.get("vertex") == "1":
        style = c.attrib.get("style", "") or ""
        # Skip if it IS the swimlane itself (already captured)
        if c.attrib["id"] == p:
            continue
        val_raw = c.attrib.get("value", "")
        # Unescape HTML
        val = html.unescape(val_raw)
        # Strip HTML tags
        val_clean = re.sub(r"<[^>]+>", " ", val)
        val_clean = re.sub(r"\s+", " ", val_clean).strip()
        if val_clean:
            entities[p]["columns"].append(val_clean)

# Edges (relationships)
edges = []
for c in cells:
    if c.attrib.get("edge") == "1":
        src = c.attrib.get("source")
        tgt = c.attrib.get("target")
        edges.append({
            "id": c.attrib["id"],
            "source": src,
            "target": tgt,
            "labels": [],
        })

# edgeLabel children carry verb / multiplicity
by_edge = {e["id"]: e for e in edges}
for c in cells:
    style = c.attrib.get("style", "") or ""
    if "edgeLabel" in style:
        p = c.attrib.get("parent", "")
        if p in by_edge:
            v = html.unescape(c.attrib.get("value", "")).strip()
            v = re.sub(r"<[^>]+>", " ", v)
            v = re.sub(r"\s+", " ", v).strip()
            if v:
                by_edge[p]["labels"].append(v)

# Print report
print("=" * 78)
print("ENTITIES ({})".format(len(entities)))
print("=" * 78)
for eid, e in sorted(entities.items(), key=lambda kv: (kv[1]["parent_group"], kv[1]["name"])):
    print(f"\n[{e['parent_group']}] {e['name']}  ({eid})")
    for col in e["columns"]:
        print(f"    - {col}")

print("\n")
print("=" * 78)
print("EDGES ({})".format(len(edges)))
print("=" * 78)
for e in edges:
    src_name = entities.get(e["source"], {}).get("name", "?" + str(e["source"]))
    tgt_name = entities.get(e["target"], {}).get("name", "?" + str(e["target"]))
    labels = " | ".join(e["labels"])
    print(f"  {src_name}  ->  {tgt_name}   [{labels}]")
