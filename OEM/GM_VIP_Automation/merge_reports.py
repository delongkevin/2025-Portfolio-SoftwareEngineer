"""
merge_reports.py  –  Consolidated HTML Report Generator for GM VIP Automation
==============================================================================
Merges all CANoe test-module XML reports and any Trace32 diagnostic XML
reports found under the GM_VIP_Automation tree into a single, easy-to-read
HTML file.

Report sources discovered automatically
----------------------------------------
1. CANoe per-module XML reports stored under  ``Test Reports/**/*.xml``
   (written by the test suite at the paths declared in the .tse files,
   e.g. Test Reports/Sanity/Sanity_report.xml).
2. Trace32 summary report at  ``Trace32/report.xml``  (optional – only
   included when the file exists).
3. Any additional  ``report.xml``  files found immediately inside the
   ``GM_VIP_RBS/`` folder (the "all-tests" roll-up written by GM_VIP_SWtest).

Usage
-----
    python merge_reports.py [--root <GM_VIP_Automation folder>]
                            [--out  <output HTML file>]

Exit codes
----------
    0  – merged report written without errors
    1  – one or more source XML files could not be parsed (details in output)

Supported CANoe XML report schemas
-----------------------------------
The script handles two common CANoe export formats:

  • ``testresults`` root element  (older format, direct ``<testcase>`` children)
  • ``testmodule``  root element  (newer format with ``<testgroup>``
    containers that hold ``<testcase>`` children)

T32 / Trace32 report format
-----------------------------
Any ``<testcase>`` or ``<step>`` elements found in Trace32 XML reports are
extracted and listed in a dedicated "Trace32 Diagnostics" section.  This
ensures T32 connection failures and breakpoint check results are always
visible in the consolidated view alongside the CANoe results.
"""

from __future__ import annotations

import argparse
import datetime
import html
import os
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class TestStep:
    name: str
    result: str          # "pass", "fail", "error", "unknown"
    description: str = ""


@dataclass
class TestCase:
    name: str
    result: str          # "pass", "fail", "error", "unknown"
    title: str = ""
    steps: List[TestStep] = field(default_factory=list)


@dataclass
class TestGroup:
    title: str
    cases: List[TestCase] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.cases)

    @property
    def passed(self) -> int:
        return sum(1 for c in self.cases if c.result == "pass")

    @property
    def failed(self) -> int:
        return sum(1 for c in self.cases if c.result in ("fail", "error"))


@dataclass
class ReportModule:
    source_file: Path
    title: str
    groups: List[TestGroup] = field(default_factory=list)
    is_t32: bool = False

    @property
    def total(self) -> int:
        return sum(g.total for g in self.groups)

    @property
    def passed(self) -> int:
        return sum(g.passed for g in self.groups)

    @property
    def failed(self) -> int:
        return sum(g.failed for g in self.groups)


# ---------------------------------------------------------------------------
# XML parsing helpers
# ---------------------------------------------------------------------------

def _normalise_result(raw: Optional[str]) -> str:
    """Map CANoe result strings to a canonical lower-case token."""
    if raw is None:
        return "unknown"
    lower = raw.strip().lower()
    if lower in ("pass", "passed", "ok", "success", "1", "true"):
        return "pass"
    if lower in ("fail", "failed", "error", "ng", "0", "false"):
        return "fail"
    return lower or "unknown"


def _text(elem: ET.Element, *tags: str) -> str:
    """Return stripped text of the first matching sub-element, or ''."""
    for tag in tags:
        sub = elem.find(tag)
        if sub is not None and sub.text:
            return sub.text.strip()
    return ""


def _parse_canoe_testresults(root: ET.Element) -> List[TestGroup]:
    """Parse a ``<testresults>`` root (older CANoe XML schema)."""
    groups: List[TestGroup] = []
    default_group = TestGroup(title="Results")

    for tc_elem in root.iter("testcase"):
        name  = tc_elem.get("name", tc_elem.get("title", "unnamed"))
        title = tc_elem.get("title", name)
        res   = _normalise_result(tc_elem.get("verdict", tc_elem.get("result")))

        steps: List[TestStep] = []
        for step_elem in tc_elem.iter("step"):
            sname = step_elem.get("name", step_elem.get("title", ""))
            sres  = _normalise_result(step_elem.get("verdict", step_elem.get("result")))
            sdesc = _text(step_elem, "description", "desc")
            steps.append(TestStep(name=sname, result=sres, description=sdesc))

        default_group.cases.append(TestCase(name=name, title=title, result=res, steps=steps))

    if default_group.cases:
        groups.append(default_group)
    return groups


def _parse_canoe_testmodule(root: ET.Element) -> List[TestGroup]:
    """Parse a ``<testmodule>`` root (newer CANoe XML schema)."""
    groups: List[TestGroup] = []

    for tg_elem in root.iter("testgroup"):
        group = TestGroup(title=tg_elem.get("title", "Group"))
        for tc_elem in tg_elem.iter("testcase"):
            name  = tc_elem.get("name", tc_elem.get("title", "unnamed"))
            title = tc_elem.get("title", name)
            res   = _normalise_result(tc_elem.get("verdict", tc_elem.get("result")))

            steps: List[TestStep] = []
            for step_elem in tc_elem.iter("step"):
                sname = step_elem.get("name", step_elem.get("title", ""))
                sres  = _normalise_result(step_elem.get("verdict", step_elem.get("result")))
                sdesc = _text(step_elem, "description", "desc")
                steps.append(TestStep(name=sname, result=sres, description=sdesc))

            group.cases.append(TestCase(name=name, title=title, result=res, steps=steps))
        if group.cases:
            groups.append(group)

    # Also pick up top-level <testcase> elements not inside any group.
    top_level = TestGroup(title="(ungrouped)")
    for tc_elem in root.findall("testcase"):
        name  = tc_elem.get("name", tc_elem.get("title", "unnamed"))
        title = tc_elem.get("title", name)
        res   = _normalise_result(tc_elem.get("verdict", tc_elem.get("result")))
        top_level.cases.append(TestCase(name=name, title=title, result=res))
    if top_level.cases:
        groups.append(top_level)

    return groups


def _parse_t32_report(root: ET.Element) -> List[TestGroup]:
    """
    Parse a Trace32 report XML into a flat group of diagnostic steps.
    T32 XML does not have a fixed schema; we collect any <testcase> /
    <step> / <result> / <verdict> elements we can find.
    """
    group = TestGroup(title="T32 Diagnostics")

    for tc_elem in root.iter("testcase"):
        name = tc_elem.get("name", tc_elem.get("title", "T32 check"))
        res  = _normalise_result(tc_elem.get("verdict", tc_elem.get("result")))

        # Capture child steps so failure details are visible in the report.
        steps: List[TestStep] = []
        for step_elem in tc_elem.iter("step"):
            sname = step_elem.get("name", step_elem.get("title", ""))
            sres  = _normalise_result(step_elem.get("verdict", step_elem.get("result")))
            sdesc = _text(step_elem, "description", "desc")
            if not sdesc and step_elem.text:
                sdesc = step_elem.text.strip()
            steps.append(TestStep(name=sname, result=sres, description=sdesc))

        group.cases.append(TestCase(name=name, title=name, result=res, steps=steps))

    # If no testcase elements, fall back to step-level entries.
    if not group.cases:
        for step_elem in root.iter("step"):
            name = step_elem.get("name", step_elem.get("title", "T32 step"))
            res  = _normalise_result(step_elem.get("verdict", step_elem.get("result")))
            desc = _text(step_elem, "description", "desc")
            if not desc and step_elem.text:
                desc = step_elem.text.strip()
            group.cases.append(TestCase(name=name, title=name, result=res,
                                        steps=[TestStep(name=name, result=res,
                                                        description=desc)]))

    return [group] if group.cases else []


def parse_report_xml(filepath: Path, is_t32: bool = False) -> Optional[ReportModule]:
    """Parse one XML file into a ReportModule.  Returns None on error."""
    try:
        tree = ET.parse(filepath)
    except ET.ParseError as exc:
        print(f"  WARNING: could not parse {filepath}: {exc}", file=sys.stderr)
        return None

    root = tree.getroot()
    tag  = root.tag.lower()

    if is_t32:
        groups = _parse_t32_report(root)
        title  = root.get("title", "Trace32")
    elif tag == "testresults":
        groups = _parse_canoe_testresults(root)
        title  = root.get("title", filepath.stem)
    elif tag in ("testmodule", "testmoduleresults"):
        groups = _parse_canoe_testmodule(root)
        title  = root.get("title", filepath.stem)
    else:
        # Unknown schema – try both parsers and take whichever yields data.
        groups = _parse_canoe_testmodule(root) or _parse_canoe_testresults(root)
        title  = root.get("title", filepath.stem)

    return ReportModule(source_file=filepath, title=title or filepath.stem,
                        groups=groups, is_t32=is_t32)


# ---------------------------------------------------------------------------
# Report discovery
# ---------------------------------------------------------------------------

def discover_reports(root: Path) -> List[ReportModule]:
    """
    Discover all report XML files under *root* and return parsed modules.

    Search order (determines display order in the HTML):
      1. Test Reports/**/*.xml  (CANoe per-module reports)
      2. GM_VIP_RBS/report.xml  (all-tests roll-up)
      3. Trace32/report.xml     (T32 diagnostics, optional)
    """
    modules: List[ReportModule] = []
    seen: set = set()

    # 1. CANoe per-module reports
    test_reports_dir = root / "Test Reports"
    if test_reports_dir.is_dir():
        for xml_path in sorted(test_reports_dir.rglob("*.xml")):
            if xml_path.resolve() in seen:
                continue
            seen.add(xml_path.resolve())
            mod = parse_report_xml(xml_path)
            if mod is not None:
                modules.append(mod)

    # 2. All-tests roll-up in GM_VIP_RBS/
    rbs_report = root / "GM_VIP_RBS" / "report.xml"
    if rbs_report.is_file() and rbs_report.resolve() not in seen:
        seen.add(rbs_report.resolve())
        mod = parse_report_xml(rbs_report)
        if mod is not None:
            mod.title = mod.title or "GM_VIP_SWtest (all)"
            modules.append(mod)

    # 3. Trace32 diagnostics
    t32_report = root / "Trace32" / "report.xml"
    if t32_report.is_file() and t32_report.resolve() not in seen:
        seen.add(t32_report.resolve())
        mod = parse_report_xml(t32_report, is_t32=True)
        if mod is not None:
            mod.title = "Trace32 Diagnostics"
            modules.append(mod)

    return modules


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

_CSS = """
:root { --color-pass: #1a7d1a; --color-fail: #b30000; --color-brand: #003580; }
body  { font-family: Arial, sans-serif; margin: 20px; color: #222; }
h1    { color: var(--color-brand); }
h2    { color: var(--color-brand); border-bottom: 2px solid var(--color-brand); padding-bottom: 4px; }
h3    { color: #555; margin-top: 12px; }
table { border-collapse: collapse; width: 100%; margin-bottom: 24px; }
th    { background: var(--color-brand); color: #fff; padding: 8px 12px; text-align: left; }
td    { padding: 6px 12px; border-bottom: 1px solid #ddd; }
tr:nth-child(even) { background: #f5f5f5; }
.pass  { color: var(--color-pass); font-weight: bold; }
.fail  { color: var(--color-fail); font-weight: bold; }
.error { color: var(--color-fail); font-weight: bold; }
.unknown { color: #888; }
.t32-section { background: #fffbe6; border-left: 4px solid #e6b800; padding: 4px 12px; }
.summary-box { display: inline-block; background: #eef4ff; border: 1px solid var(--color-brand);
               border-radius: 6px; padding: 12px 24px; margin-bottom: 20px; }
.summary-box td { border: none; padding: 3px 16px; }
.grand-pass  { color: var(--color-pass); font-size: 1.2em; font-weight: bold; }
.grand-fail  { color: var(--color-fail); font-size: 1.2em; font-weight: bold; }
"""

_RESULT_CLASS = {
    "pass":    "pass",
    "fail":    "fail",
    "error":   "error",
    "unknown": "unknown",
}


def _result_cell(result: str) -> str:
    css = _RESULT_CLASS.get(result, "unknown")
    return f'<span class="{css}">{html.escape(result.upper())}</span>'


def generate_html(modules: List[ReportModule], generated_at: datetime.datetime) -> str:
    grand_total  = sum(m.total  for m in modules)
    grand_passed = sum(m.passed for m in modules)
    grand_failed = sum(m.failed for m in modules)

    lines: List[str] = []
    lines.append("<!DOCTYPE html>")
    lines.append("<html lang='en'><head>")
    lines.append("<meta charset='UTF-8'>")
    lines.append("<title>GM VIP Automation – Consolidated Test Report</title>")
    lines.append(f"<style>{_CSS}</style>")
    lines.append("</head><body>")
    lines.append("<h1>GM VIP Automation – Consolidated Test Report</h1>")
    lines.append(f"<p>Generated: {html.escape(generated_at.strftime('%Y-%m-%d %H:%M:%S'))}</p>")

    # Grand summary
    overall_class = "grand-pass" if grand_failed == 0 else "grand-fail"
    lines.append('<div class="summary-box"><table>')
    lines.append(f'<tr><td>Total tests</td><td><b>{grand_total}</b></td></tr>')
    lines.append(f'<tr><td>Passed</td><td class="pass"><b>{grand_passed}</b></td></tr>')
    lines.append(f'<tr><td>Failed / Error</td><td class="fail"><b>{grand_failed}</b></td></tr>')
    overall_text = "ALL PASSED" if grand_failed == 0 else f"{grand_failed} FAILURE(S)"
    lines.append(f'<tr><td>Overall</td><td class="{overall_class}">{overall_text}</td></tr>')
    lines.append("</table></div>")

    if not modules:
        lines.append("<p><em>No test reports found. Run the test suites first.</em></p>")
        lines.append("</body></html>")
        return "\n".join(lines)

    # Table of contents
    lines.append("<h2>Modules</h2><ul>")
    for idx, mod in enumerate(modules):
        anchor = f"mod-{idx}"
        status = "✅" if mod.failed == 0 and mod.total > 0 else ("❌" if mod.failed > 0 else "–")
        lines.append(
            f'<li><a href="#{anchor}">{status} {html.escape(mod.title)}</a>'
            f'  ({mod.passed}/{mod.total} passed)</li>'
        )
    lines.append("</ul>")

    # Per-module details
    for idx, mod in enumerate(modules):
        anchor = f"mod-{idx}"
        section_class = "t32-section" if mod.is_t32 else ""
        rel_path = mod.source_file.name
        lines.append(f'<h2 id="{anchor}">{html.escape(mod.title)}</h2>')
        if section_class:
            lines.append(f'<div class="{section_class}">')
        lines.append(
            f'<p>Source: <code>{html.escape(str(mod.source_file))}</code> &nbsp;|&nbsp; '
            f'{mod.passed} passed, {mod.failed} failed / {mod.total} total</p>'
        )

        if not mod.groups:
            lines.append("<p><em>No test-case data found in this report.</em></p>")
        else:
            for group in mod.groups:
                lines.append(f"<h3>{html.escape(group.title)}</h3>")
                lines.append("<table>")
                lines.append("<tr><th>Test Case</th><th>Result</th></tr>")
                for case in group.cases:
                    display = html.escape(case.title or case.name)
                    lines.append(f"<tr><td>{display}</td><td>{_result_cell(case.result)}</td></tr>")

                    # Expand failing steps inline (T32 detail)
                    for step in case.steps:
                        if step.result in ("fail", "error"):
                            desc = html.escape(step.description or step.name)
                            lines.append(
                                f'<tr style="background:#fff0f0"><td>&nbsp;&nbsp;↳ '
                                f'<em>{html.escape(step.name)}</em>: {desc}</td>'
                                f'<td>{_result_cell(step.result)}</td></tr>'
                            )
                lines.append("</table>")

        if section_class:
            lines.append("</div>")

    lines.append("</body></html>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Merge CANoe and Trace32 test reports into one HTML file."
    )
    parser.add_argument(
        "--root", "-r",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Root directory of GM_VIP_Automation (default: same folder as this script)",
    )
    parser.add_argument(
        "--out", "-o",
        type=Path,
        default=None,
        help=(
            "Output HTML file path. "
            "Default: <root>/Test Reports/consolidated_report.html"
        ),
    )
    args = parser.parse_args()
    root: Path = args.root.resolve()

    if not root.is_dir():
        print(f"ERROR: root directory not found: {root}", file=sys.stderr)
        return 1

    out_path: Path = args.out or (root / "Test Reports" / "consolidated_report.html")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Scanning for reports under: {root}")
    modules = discover_reports(root)

    if not modules:
        print("  No report XML files found. Run the test suites first.", file=sys.stderr)

    for mod in modules:
        status = "OK" if mod.failed == 0 else "FAIL"
        t32_tag = " [T32]" if mod.is_t32 else ""
        print(f"  [{status}]{t32_tag} {mod.source_file.relative_to(root)}"
              f"  –  {mod.passed}/{mod.total} passed")

    html_content = generate_html(modules, datetime.datetime.now())

    try:
        out_path.write_text(html_content, encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: could not write {out_path}: {exc}", file=sys.stderr)
        return 1

    print(f"\nConsolidated report written to: {out_path}")

    total_failed = sum(m.failed for m in modules)
    return 1 if total_failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
