#!/usr/bin/env python3
"""Generate a markdown summary of test results for GitHub Actions."""

import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def parse_junit_xml(xml_path: Path) -> dict:
    """Parse JUnit XML and extract test results."""
    tree = ET.parse(xml_path)
    root = tree.getroot()
    
    results = {
        "passed": [],
        "failed": [],
        "xfailed": [],
        "skipped": [],
    }
    
    for testcase in root.iter("testcase"):
        state_name = testcase.get("name", "Unknown")
        
        # Check test status
        failure = testcase.find("failure")
        skipped = testcase.find("skipped")
        error = testcase.find("error")
        
        if failure is not None:
            message = failure.get("message", "")
            if "CRITICAL" in message:
                results["failed"].append((state_name, message))
            else:
                results["xfailed"].append((state_name, message))
        elif skipped is not None:
            message = skipped.get("message", "")
            results["skipped"].append((state_name, message))
        elif error is not None:
            message = error.get("message", "")
            results["failed"].append((state_name, message))
        else:
            results["passed"].append(state_name)
    
    return results


def generate_markdown_summary(results: dict) -> str:
    """Generate a markdown summary table."""
    total = len(results["passed"]) + len(results["failed"]) + len(results["xfailed"]) + len(results["skipped"])
    passed = len(results["passed"])
    failed = len(results["failed"])
    xfailed = len(results["xfailed"])
    skipped = len(results["skipped"])
    
    md = "## 📊 WMS Download Test Results\n\n"
    
    # Summary
    md += "### Summary\n\n"
    md += f"- **Total States Tested**: {total}\n"
    md += f"- ✅ **Passed**: {passed}\n"
    md += f"- ❌ **Failed (Critical)**: {failed}\n"
    md += f"- ⚠️ **Expected Failures**: {xfailed}\n"
    md += f"- ⏭️ **Skipped**: {skipped}\n\n"
    
    if failed > 0:
        md += "🚨 **CRITICAL**: Bayern and/or Baden-Württemberg failed!\n\n"
    else:
        md += "✅ **All critical states (Bayern, Baden-Württemberg) passed!**\n\n"
    
    # Passed states
    if results["passed"]:
        md += "### ✅ Working States\n\n"
        md += "| State | Status |\n"
        md += "|-------|--------|\n"
        for state in sorted(results["passed"]):
            md += f"| {state} | ✅ Passed |\n"
        md += "\n"
    
    # Failed states (critical)
    if results["failed"]:
        md += "### ❌ Failed States (Critical)\n\n"
        md += "| State | Error |\n"
        md += "|-------|-------|\n"
        for state, error in sorted(results["failed"]):
            error_short = error.split("\n")[0][:100]
            md += f"| {state} | {error_short} |\n"
        md += "\n"
    
    # Expected failures (non-critical)
    if results["xfailed"]:
        md += "### ⚠️ Expected Failures (Non-Critical)\n\n"
        md += "| State | Error |\n"
        md += "|-------|-------|\n"
        for state, error in sorted(results["xfailed"]):
            error_short = error.split("\n")[0][:100]
            md += f"| {state} | {error_short} |\n"
        md += "\n"
    
    # Skipped
    if results["skipped"]:
        md += "### ⏭️ Skipped States\n\n"
        md += "| State | Reason |\n"
        md += "|-------|--------|\n"
        for state, reason in sorted(results["skipped"]):
            md += f"| {state} | {reason} |\n"
        md += "\n"
    
    md += "---\n"
    md += "*Critical states: Bayern, Baden-Württemberg*\n"
    
    return md


def main():
    """Main entry point."""
    xml_path = Path("test-results.xml")
    
    if not xml_path.exists():
        print("❌ test-results.xml not found")
        sys.exit(1)
    
    results = parse_junit_xml(xml_path)
    markdown = generate_markdown_summary(results)
    
    # Write to GitHub Actions summary
    github_summary = Path(sys.environ.get("GITHUB_STEP_SUMMARY", "summary.md"))
    with open(github_summary, "a") as f:
        f.write(markdown)
    
    print(markdown)
    
    # Exit with failure if critical states failed
    if results["failed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
