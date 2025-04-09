import re

# Regex to match diff hunk headers like: @@ -10,7 +9,6 @@
DIFF_HUNK_HEADER_REGEX = re.compile(
    r'^@@ -(?P<old_start>\d+)(?:,(?P<old_count>\d+))? '
    r'\+(?P<new_start>\d+)(?:,(?P<new_count>\d+))? @@'
)


def parse_unified_diff(patch_text):
    """
    Parses the unified diff text for a single file.

    Returns:
      - line_map: dict mapping 'new-file line number' -> 'GitHub diff position'
      - new_lines_text: dict mapping 'new-file line number' -> the actual code text (minus '+' sign)
    """
    lines = patch_text.splitlines()
    diff_position = 0  # 1-based index for each line in the patch
    line_map = {}
    new_lines_text = {}

    current_old_line = None
    current_new_line = None
    found_header = False

    for line in lines:
        diff_position += 1  # Each line (including hunk header) increments this

        match = DIFF_HUNK_HEADER_REGEX.match(line)
        if match:
            # Found a hunk header
            old_start = int(match.group('old_start'))
            old_count = match.group('old_count')
            new_start = int(match.group('new_start'))
            new_count = match.group('new_count')

            old_count = int(old_count) if old_count else 1
            new_count = int(new_count) if new_count else 1

            current_old_line = old_start
            current_new_line = new_start
            found_header = True

            continue

        if not found_header:
            # Don't do any parsing until the first hunk is found
            # This allows it to skip headers and any other junk which may be included
            continue

        if line.startswith('+'):
            # This line is newly added (exists in the new file)
            # Remove the leading '+' so we can match actual code text
            code_text = line[1:].lstrip()
            line_map[current_new_line] = diff_position
            new_lines_text[current_new_line] = code_text
            current_new_line += 1
        elif line.startswith('-'):
            # This line is removed in the new file
            current_old_line += 1
        else:
            # Context line => present in both old & new
            code_text = line.lstrip()
            line_map[current_new_line] = diff_position
            new_lines_text[current_new_line] = code_text
            current_old_line += 1
            current_new_line += 1

    return line_map, new_lines_text
