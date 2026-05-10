from util.git import parse_unified_diff


def test_parse_unified_diff_maps_added_and_context_lines():
    patch = """diff --git a/app.py b/app.py
index 0000000..1111111 100644
--- a/app.py
+++ b/app.py
@@ -1,3 +1,4 @@
 import os
-query = "safe"
+query = request.args["q"]
+db.execute("select * from users where name = " + query)
 print(query)
"""

    line_map, new_lines_text = parse_unified_diff(patch)

    assert new_lines_text == {
        1: "import os",
        2: 'query = request.args["q"]',
        3: 'db.execute("select * from users where name = " + query)',
        4: "print(query)",
    }
    assert set(line_map) == {1, 2, 3, 4}
    assert line_map[2] < line_map[3]


def test_parse_unified_diff_ignores_headers_before_first_hunk():
    line_map, new_lines_text = parse_unified_diff(
        """diff --git a/app.py b/app.py
metadata that should not be parsed
@@ -0,0 +1,2 @@
+first = True
+second = True
"""
    )

    assert new_lines_text == {1: "first = True", 2: "second = True"}
    assert set(line_map) == {1, 2}
