import logging
import os
import fnmatch

#TODO: Make this recognise more gitignore patterns, like simple directory matching with /
#TODO: Document in README
#TODO: Switch to verbose logging only

DEFAULT_EXTENSIONS = [
    ".c", ".cpp", ".h", ".hpp",
    ".py", ".js", ".jsx", ".ts", ".tsx",
    ".java", ".cs", ".go", ".php", ".rb",
    ".swift", ".scala", ".kt", ".m", ".mm",
    ".rs", ".sh"
]

logger = logging.getLogger(__name__)

def load_patterns(filename):
    """
    Loads glob-style patterns from a file.
    Returns a list of patterns.
    """
    if not os.path.exists(filename):
        return []

    logger.debug(f"load_patterns: Found {filename}, processing...")
    with open(filename, "r") as f:
        lines = f.readlines()

    return [
        line.strip()
        for line in lines
        if line.strip() and not line.strip().startswith("#")
    ]

def pattern_match(filepath, patterns):
    normalized_path = filepath.replace("\\", "/")
    return any(fnmatch.fnmatch(normalized_path, pattern) for pattern in patterns)

#             if file_exceeds_line_length_limit(file_content=scm.read_file_contents(), patch_text=patch_text, max_line_length=args.max_line_length):

def file_exceeds_line_length_limit(file_content: str, patch_text: str, max_line_length: int = 1000):
    """
    Checks if any line in the file exceeds max_length.
    Returns True if all lines are within the limit, False otherwise.
    """
    for line in file_content.splitlines():
        if len(line) > max_line_length:
            return True
        
    for line in patch_text.splitlines():
        if len(line) > max_line_length:
            return True

    return False

def filename_included(filepath: str):
    """
    Returns True if the file is included in includelist and not explicitly ignored in ignorelist.
    """
    # Check include/ignore rules
    logger.debug(f"should_process: {filepath}")
    if not pattern_match(filepath, include_patterns):
        return False
    if pattern_match(filepath, ignore_patterns):
        return False
           
    return True

include_patterns = load_patterns("saist.include")
if not include_patterns:
    # Fallback to extension-based glob patterns like **/*.py
    include_patterns = [f"*{ext}" for ext in DEFAULT_EXTENSIONS]
ignore_patterns = load_patterns("saist.ignore")

logger.info(f"include_patterns: {include_patterns}\nignore_patterns:{ignore_patterns}")
