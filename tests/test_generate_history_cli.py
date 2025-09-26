import logging

from scripts import generate_history


def test_parser_accepts_debug_scan_flag() -> None:
    parser = generate_history._build_parser()  # type: ignore[attr-defined]
    args = parser.parse_args(["--debug-scan"])

    assert args.debug_scan is True
    assert args.log_level is None


def test_debug_scan_defaults_to_debug_level() -> None:
    parser = generate_history._build_parser()  # type: ignore[attr-defined]
    args = parser.parse_args(["--debug-scan"])

    level = generate_history._determine_log_level(args)  # type: ignore[attr-defined]

    assert level == logging.DEBUG


def test_explicit_log_level_overrides_debug_scan() -> None:
    parser = generate_history._build_parser()  # type: ignore[attr-defined]
    args = parser.parse_args(["--debug-scan", "--log-level", "WARNING"])

    level = generate_history._determine_log_level(args)  # type: ignore[attr-defined]

    assert level == logging.WARNING
