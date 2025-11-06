import logging
from pathlib import Path
from gitignore_parser import parse_gitignore_str

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
    def __init__(self, include_patterns: list, exclude_patterns: list, include_rules_file: str | Path = "saist.include", exclude_rules_file: str | Path = "saist.ignore"):
        """
        Load include/exclude rules from disk and command-line arguments
        """
        # Load initial rules from disk
        self.include_patterns = self.__load_rule_file(include_rules_file)
        self.exclude_patterns = self.__load_rule_file(exclude_rules_file)

        logger.debug(f"Processing inclusion rules from {include_rules_file} and exclusion rules from {exclude_rules_file}")

        if not self.include_patterns:
            # If no rules in saist.include, fallback to extension-based glob patterns like **/*.py
            logger.debug("No saist.include, using defaults")
            self.include_patterns = [f"*{ext}" for ext in DEFAULT_EXTENSIONS]

        # Extend list of patterns loaded from disk / defaults with additional patterns from CLI arguments
        # The list comprehensions here flatten the pattern arguments into a single list as argparse will return a nested list
        if include_patterns:
            self.include_patterns.extend([pattern for item in include_patterns for pattern in item])

        if exclude_patterns:
            self.exclude_patterns.extend([pattern for item in exclude_patterns for pattern in item])
        
        logger.debug(f"include_patterns: {self.include_patterns}\nignore_patterns:{self.exclude_patterns}")

        # Convert include/exclude pattern lists into a gitignore format for parsing with gitignore_parser
        exclude_gitignore_str = "\n".join(self.exclude_patterns)
        include_gitignore_str = "\n".join(self.include_patterns)

        # Define functions for checking filenames against exclusion/inclusion lists in gitignore format
        self.__exclusion_matches = parse_gitignore_str(exclude_gitignore_str, base_dir=Path(exclude_rules_file).parent)
        self.__inclusion_matches = parse_gitignore_str(include_gitignore_str, base_dir=Path(include_rules_file).parent)

    def __load_rule_file(self, file_path: str | Path):
        """
        Load a exclude/include file from disk
        """
        file_path = Path(file_path)
        if file_path.exists():
            with open(file_path, 'r') as fp:
                return fp.readlines()
        else:
            return []

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
        if self.__exclusion_matches(filepath):
            return False
        if not self.__inclusion_matches(filepath):
            return False
            
        return True



