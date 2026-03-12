"""
validate_capl.py - Pre-deployment CAPL syntax consistency checker
==================================================================
Scans all .can/.cin files under GM_VIP_Automation and reports structural
issues that would prevent Vector CANoe from compiling them.  Run this
script before deploying to each of the 20 test benches to verify that
the source tree is internally consistent.

Checks performed
----------------
1. Bracket balance  – matched { } [ ] ( ) across each file.
2. Include existence – every #include path resolves to a file on disk.
3. Declarations     – every testcase / testfunction / export testfunction
                      declaration has a paired opening brace.
4. Cross-file refs  – every <capltestcase name="..."/> in Testsuite_Environment
                      XML files has a matching testcase definition in a .can file.
5. CAPL API names   – detects known incorrect/misspelled CAPL built-in function
                      names that cause CANoe parse errors at compile time
                      (e.g. testStepfail → testStepFail).

Usage
-----
    python validate_capl.py [--root <GM_VIP_Automation folder>]

Exit code
---------
    0  – no issues found
    1  – one or more issues detected (details printed to stdout)
"""

import argparse
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _strip_line_comments(text: str) -> str:
    """Remove // … comments (but not inside strings)."""
    result = []
    i = 0
    in_string = False
    while i < len(text):
        ch = text[i]
        if ch == '"' and (i == 0 or text[i - 1] != '\\'):
            in_string = not in_string
        if not in_string and ch == '/' and i + 1 < len(text) and text[i + 1] == '/':
            # skip to end of line
            while i < len(text) and text[i] != '\n':
                i += 1
            continue
        result.append(ch)
        i += 1
    return ''.join(result)


def _strip_block_comments(text: str) -> str:
    """Remove /* … */ block comments (but not inside strings)."""
    result = []
    i = 0
    in_string = False
    while i < len(text):
        ch = text[i]
        # Track string literal state to avoid stripping comment markers inside strings.
        if ch == '"' and (i == 0 or text[i - 1] != '\\'):
            in_string = not in_string
        # Only treat /* as a comment start when we're not inside a string.
        if not in_string and text[i:i + 2] == '/*':
            i += 2
            while i < len(text) and text[i:i + 2] != '*/':
                if text[i] == '\n':
                    result.append('\n')  # preserve line numbers
                i += 1
            # Skip the closing */
            if i < len(text):
                i += 2
        else:
            result.append(ch)
            i += 1
    return ''.join(result)


def strip_comments(text: str) -> str:
    text = _strip_block_comments(text)
    text = _strip_line_comments(text)
    return text


# ---------------------------------------------------------------------------
# Check 1 – bracket balance
# ---------------------------------------------------------------------------

def check_bracket_balance(filepath: Path, text: str) -> list[str]:
    """Return a list of error strings for unmatched brackets (ignores string literals)."""
    issues = []
    pairs = {')': '(', ']': '[', '}': '{'}
    openers = set('({[')
    stack = []
    flat = text

    # Build line start offsets for efficient lineno/col lookup
    line_start_offsets = [0]
    for idx, ch in enumerate(flat):
        if ch == '\n':
            line_start_offsets.append(idx + 1)

    def offset_to_linecol(offset: int):
        lo, hi = 0, len(line_start_offsets) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if line_start_offsets[mid] <= offset:
                lo = mid
            else:
                hi = mid - 1
        return lo + 1, offset - line_start_offsets[lo] + 1

    i = 0
    n = len(flat)
    in_string = False
    while i < n:
        ch = flat[i]
        # Enter string literal
        if ch == '"' and not in_string:
            in_string = True
            i += 1
            continue
        # Inside string literal
        if in_string:
            if ch == '\\':
                i += 2  # skip escaped character
                continue
            if ch == '"':
                in_string = False
            i += 1
            continue
        # Normal code — check brackets
        if ch in openers:
            lineno, col = offset_to_linecol(i)
            stack.append((ch, lineno, col))
        elif ch in pairs:
            expected = pairs[ch]
            lineno, col = offset_to_linecol(i)
            if not stack:
                issues.append(
                    f"  {filepath}:{lineno}:{col}: unmatched closing '{ch}' (no opener on stack)"
                )
            elif stack[-1][0] != expected:
                issues.append(
                    f"  {filepath}:{lineno}:{col}: mismatched '{ch}' — expected close for"
                    f" '{stack[-1][0]}' opened at line {stack[-1][1]}"
                )
                stack.pop()
            else:
                stack.pop()
        i += 1
    for opener, lineno, col in stack:
        issues.append(
            f"  {filepath}:{lineno}:{col}: unclosed '{opener}' — no matching close found"
        )
    return issues


# ---------------------------------------------------------------------------
# Check 2 – #include existence
# ---------------------------------------------------------------------------

_INCLUDE_RE = re.compile(r'#include\s+"([^"]+)"')


def check_includes(filepath: Path, text: str) -> list[str]:
    """Return a list of error strings for #includes that cannot be resolved."""
    issues = []
    parent = filepath.parent
    for lineno, line in enumerate(text.splitlines(), start=1):
        m = _INCLUDE_RE.search(line)
        if not m:
            continue
        inc_path_raw = m.group(1).replace('\\', os.sep).replace('/', os.sep)
        resolved = (parent / inc_path_raw).resolve()
        if not resolved.exists():
            issues.append(
                f"  {filepath}:{lineno}: #include not found: '{m.group(1)}'"
                f" (resolved to {resolved})"
            )
    return issues


# ---------------------------------------------------------------------------
# Check 3 – function declaration / opening brace
# ---------------------------------------------------------------------------

# Matches declarations ending on the same line with no opening brace yet
_DECL_NO_BRACE_RE = re.compile(
    r'^(?:export\s+)?(?:testfunction|testcase)\s+(\w+)\s*\([^)]*\)\s*$'
)


def check_declarations(filepath: Path, text: str) -> list[str]:
    """
    Verify that every testcase/testfunction declaration is followed by an
    opening brace within the next few non-blank lines.
    """
    issues = []
    lines = text.splitlines()
    for lineno, line in enumerate(lines, start=1):
        stripped = line.strip()
        # Check for declaration pattern without opening brace on same line
        m = _DECL_NO_BRACE_RE.match(stripped)
        if not m:
            continue
        func_name = m.group(1)
        # Look ahead up to 3 lines for the opening brace
        found_brace = False
        for ahead in range(1, 4):
            if lineno - 1 + ahead < len(lines):
                ahead_line = lines[lineno - 1 + ahead].strip()
                if ahead_line.startswith('{'):
                    found_brace = True
                    break
                if ahead_line and not ahead_line.startswith('//'):
                    break  # non-blank, non-comment line that isn't {
        if not found_brace:
            issues.append(
                f"  {filepath}:{lineno}: declaration of '{func_name}' has no"
                " opening brace within 3 lines"
            )
    return issues


# ---------------------------------------------------------------------------
# Check 4 – cross-file: XML testcase names vs .can definitions
# ---------------------------------------------------------------------------

_TESTCASE_DEF_RE = re.compile(
    r'(?:export\s+)?testcase\s+(\w+)\s*\('
)


def collect_testcase_names_from_can(can_files: list[Path]) -> dict[str, Path]:
    """Return mapping of testcase name → file for all .can files."""
    defined: dict[str, Path] = {}
    for fp in can_files:
        try:
            raw = fp.read_text(encoding='latin-1', errors='replace')
        except OSError:
            continue
        cleaned = strip_comments(raw)
        for m in _TESTCASE_DEF_RE.finditer(cleaned):
            defined[m.group(1)] = fp
    return defined


def collect_testcase_refs_from_xml(xml_files: list[Path]) -> dict[str, Path]:
    """Return mapping of capltestcase name → XML file."""
    refs: dict[str, Path] = {}
    for fp in xml_files:
        try:
            tree = ET.parse(fp)
        except ET.ParseError:
            continue
        root = tree.getroot()
        for elem in root.iter('capltestcase'):
            name = elem.get('name', '').strip()
            if name:
                refs[name] = fp
    return refs


def check_xml_vs_can_consistency(
    defined: dict[str, Path], refs: dict[str, Path]
) -> list[str]:
    """Report XML references that have no matching testcase definition."""
    issues = []
    for name, xml_fp in sorted(refs.items()):
        if name not in defined:
            issues.append(
                f"  {xml_fp}: <capltestcase name=\"{name}\"> has no"
                " matching testcase definition in any .can file"
            )
    return issues


# ---------------------------------------------------------------------------
# Check 5 – known CAPL API name typos / case errors
# ---------------------------------------------------------------------------
#
# Maps each incorrect (misspelled or wrong-case) identifier to the correct one.
# These cause CANoe parse errors at compile time and are easy to miss by eye
# because CAPL function names are case-sensitive.
#
_CAPL_API_TYPOS: dict[str, str] = {
    # testStepFail is the correct CAPL built-in; 'testStepfail' (lowercase f)
    # triggers a parse error in every CANoe version.
    "testStepfail":  "testStepFail",
    # testStepPass is the correct CAPL built-in; 'testSteppass' (lowercase p)
    # is an undefined identifier and causes a parse error.
    "testSteppass":  "testStepPass",
    # testCaseFail is the correct CAPL built-in; lowercase variants are invalid.
    "testCasefail":  "testCaseFail",
    "testcasefail":  "testCaseFail",
}

# Pre-compiled regex: word-boundary match for each incorrect token so we don't
# flag occurrences inside longer identifiers.
_CAPL_TYPO_RE = re.compile(
    r'\b(' + '|'.join(re.escape(k) for k in _CAPL_API_TYPOS) + r')\b'
)


def check_capl_api_names(filepath: Path, text: str) -> list[str]:
    """Return error strings for known CAPL built-in name typos / case errors."""
    issues = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for m in _CAPL_TYPO_RE.finditer(line):
            wrong = m.group(1)
            correct = _CAPL_API_TYPOS[wrong]
            issues.append(
                f"  {filepath}:{lineno}:{m.start() + 1}: "
                f"incorrect CAPL API name '{wrong}' — use '{correct}' instead"
            )
    return issues


# ---------------------------------------------------------------------------
# Main driver
# ---------------------------------------------------------------------------

def find_files(root: Path, extensions: list[str]) -> list[Path]:
    result = []
    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            if any(fn.lower().endswith(ext) for ext in extensions):
                result.append(Path(dirpath) / fn)
    return sorted(result)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pre-deployment CAPL syntax consistency checker for GM VIP Automation"
    )
    parser.add_argument(
        '--root',
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Root directory of GM_VIP_Automation (default: same folder as this script)",
    )
    args = parser.parse_args()
    root: Path = args.root.resolve()

    if not root.is_dir():
        print(f"ERROR: root directory not found: {root}", file=sys.stderr)
        return 1

    capl_files = find_files(root, ['.can', '.cin'])
    testsuite_dir = root / 'Testsuite_Environment'
    if not testsuite_dir.is_dir():
        print(
            f"WARNING: Testsuite_Environment folder not found under {root}. "
            "Cross-file XML-vs-CAPL consistency check will be skipped.",
            file=sys.stderr,
        )
        xml_files = []
    else:
        xml_files = find_files(testsuite_dir, ['.xml'])

    all_issues: list[str] = []

    print(f"Scanning {len(capl_files)} CAPL file(s) and {len(xml_files)} XML file(s) under {root}\n")

    # ---- Per-file checks ----
    for fp in capl_files:
        try:
            raw = fp.read_text(encoding='latin-1', errors='replace')
        except OSError as exc:
            all_issues.append(f"  {fp}: could not read file: {exc}")
            continue

        cleaned = strip_comments(raw)

        file_issues = []
        file_issues += check_bracket_balance(fp, cleaned)
        file_issues += check_includes(fp, raw)       # raw: keep line numbers accurate
        file_issues += check_declarations(fp, cleaned)
        file_issues += check_capl_api_names(fp, cleaned)

        if file_issues:
            print(f"[FAIL] {fp.relative_to(root)}")
            for issue in file_issues:
                print(issue)
            print()
            all_issues += file_issues
        else:
            print(f"[OK]   {fp.relative_to(root)}")

    # ---- Cross-file checks ----
    if xml_files:
        print("\n--- Cross-file consistency (XML test suites vs .can definitions) ---")
        defined = collect_testcase_names_from_can(capl_files)
        refs = collect_testcase_refs_from_xml(xml_files)
        cross_issues = check_xml_vs_can_consistency(defined, refs)
        if cross_issues:
            for issue in cross_issues:
                print(issue)
            all_issues += cross_issues
        else:
            print("[OK]   All XML <capltestcase> names resolved to a .can definition.")

    # ---- Summary ----
    print(f"\n{'='*60}")
    if all_issues:
        print(f"RESULT: {len(all_issues)} issue(s) found. Fix before deploying to benches.")
        return 1
    else:
        print("RESULT: No issues found. CAPL files are consistent.")
        return 0


if __name__ == '__main__':
    sys.exit(main())
