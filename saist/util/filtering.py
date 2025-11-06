import logging
import os
import fnmatch

#TODO: Make this recognise more gitignore patterns, like simple directory matching with /
#TODO: Document in README

DEFAULT_EXTENSIONS = [
    ".c", ".cpp", ".h", ".hpp",
    ".py", ".js", ".jsx", ".ts", ".tsx",
    ".java", ".cs", ".go", ".php", ".rb",
    ".swift", ".scala", ".kt", ".m", ".mm",
    ".rs", ".sh"
]

logger = logging.getLogger(__name__)

class FilterRules:
    def __init__(self, include_patterns: list, exclude_patterns: list, include_rules_file: str = "saist.include", exclude_rules_file: str = "saist.ignore"):
        """
        Load include/exclude rules from disk and command-line arguments
        """
        # Load initial rules from disk
        self.include_patterns = self.__load_patterns(include_rules_file)
        self.exclude_patterns = self.__load_patterns(exclude_rules_file)

        if not self.include_patterns:
            # If no rules in saist.include, fallback to extension-based glob patterns like **/*.py
            logging.debug("No include arguments provided and no saist.include, using defaults")
            self.include_patterns = [f"*{ext}" for ext in DEFAULT_EXTENSIONS]

        # Extend list of patterns loaded from disk / defaults with additional patterns from CLI arguments
        # The list comprehensions here flatten the pattern arguments into a single list as argparse will return a nested list
        if include_patterns:
            self.include_patterns.extend([pattern for item in include_patterns for pattern in item])

        if exclude_patterns:
            self.exclude_patterns.extend([pattern for item in exclude_patterns for pattern in item])
        
        logger.debug(f"include_patterns: {self.include_patterns}\nignore_patterns:{self.exclude_patterns}")

    def __load_patterns(self, filename: str) -> list:
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

    def __pattern_match(self, filepath: str, patterns: list) -> bool:
        """
        Check if filename matches any provided patterns
        Returns True if any match.
        """
        normalized_path = filepath.replace("\\", "/")
        return any(fnmatch.fnmatch(normalized_path, pattern) for pattern in patterns)

    def file_exceeds_line_length_limit(self, file_content: str, patch_text: str, max_line_length: int = 1000) -> bool:
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

    def filename_included(self, filepath: str) -> bool:
        """
        Returns True if the file is included in includelist and not explicitly ignored in ignorelist.
        """
        if not self.__pattern_match(filepath, self.include_patterns):
            return False
        if self.__pattern_match(filepath, self.exclude_patterns):
            return False
            
        return True



