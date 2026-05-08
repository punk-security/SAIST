from util.filtering import FilterRules


def test_filter_rules_apply_include_and_exclude_files(tmp_path):
    include_file = tmp_path / "saist.include"
    exclude_file = tmp_path / "saist.ignore"
    include_file.write_text("src/**/*.py\nREADME.md\n", encoding="utf-8")
    exclude_file.write_text("src/generated/\n", encoding="utf-8")

    rules = FilterRules(
        include_patterns=None,
        exclude_patterns=None,
        include_rules_file=include_file,
        exclude_rules_file=exclude_file,
    )

    assert rules.filename_included(str(tmp_path / "src" / "app.py"))
    assert rules.filename_included(str(tmp_path / "README.md"))
    assert not rules.filename_included(str(tmp_path / "src" / "generated" / "client.py"))
    assert not rules.filename_included(str(tmp_path / "src" / "app.js"))


def test_filter_rules_allow_cli_patterns_to_extend_file_rules(tmp_path):
    include_file = tmp_path / "saist.include"
    exclude_file = tmp_path / "saist.ignore"
    include_file.write_text("src/**/*.py\n", encoding="utf-8")
    exclude_file.write_text("", encoding="utf-8")

    rules = FilterRules(
        include_patterns=[["tools/**/*.sh"]],
        exclude_patterns=[["**/danger.sh"]],
        include_rules_file=include_file,
        exclude_rules_file=exclude_file,
    )

    assert rules.filename_included(str(tmp_path / "src" / "app.py"))
    assert rules.filename_included(str(tmp_path / "tools" / "run.sh"))
    assert not rules.filename_included(str(tmp_path / "tools" / "danger.sh"))


def test_file_exceeds_line_length_limit_checks_file_and_patch_text():
    rules = FilterRules(include_patterns=None, exclude_patterns=None)

    assert rules.file_exceeds_line_length_limit("short\n", "+short\n", max_line_length=10) is False
    assert rules.file_exceeds_line_length_limit("x" * 11, "+short\n", max_line_length=10) is True
    assert rules.file_exceeds_line_length_limit("short\n", "+" + "x" * 11, max_line_length=10) is True
