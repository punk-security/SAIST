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

def should_process(filepath):
    """
    Returns True if the file should be processed (included AND not ignored).
    """
    logger.debug(f"should_process: {filepath}")
    if not pattern_match(filepath, include_patterns):
        return False
    if pattern_match(filepath, ignore_patterns):
        return False
    return True

include_patterns = load_patterns("saist.include")
if not include_patterns:
    # Fallback to extension-based glob patterns like **/*.py
    include_patterns = [f"**/*{ext}" for ext in DEFAULT_EXTENSIONS] + [f"*{ext}" for ext in DEFAULT_EXTENSIONS]
ignore_patterns = load_patterns("saist.ignore")

logger.info(f"include_patterns: {include_patterns}\nignore_patterns:{ignore_patterns}")
