#!/usr/bin/env python3
"""Run stdlib unittest discovery with a JUnit XML report, including subtest failures."""
import argparse
from pathlib import Path
import sys
import time
import unittest
import xml.etree.ElementTree as ET


class JUnitResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cases = []

    def startTest(self, test):
        super().startTest(test)
        self.started = time.monotonic()
        self.case = ET.Element("testcase", name=test.id(), classname=type(test).__name__)

    def stopTest(self, test):
        self.case.set("time", str(round(time.monotonic() - self.started, 4)))
        self.cases.append(self.case)
        self.case = None
        super().stopTest(test)

    def case_for(self, test):
        if getattr(self, "case", None) is not None:
            return self.case
        # setUpClass/setUpModule errors can arrive without startTest.
        case = ET.Element("testcase", name=test.id(), classname="fixture")
        self.cases.append(case)
        return case

    def addFailure(self, test, err):
        super().addFailure(test, err)
        ET.SubElement(self.case_for(test), "failure").text = self._exc_info_to_string(err, test)

    def addError(self, test, err):
        super().addError(test, err)
        ET.SubElement(self.case_for(test), "error").text = self._exc_info_to_string(err, test)

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        ET.SubElement(self.case_for(test), "skipped", message=reason)

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        ET.SubElement(self.case_for(test), "skipped", message="expected failure")

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        ET.SubElement(self.case_for(test), "failure", message="unexpected success")

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err is not None:
            ET.SubElement(self.case_for(test), "failure", message=str(subtest)).text = self._exc_info_to_string(err, test)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="tests")
    parser.add_argument("--pattern", default="test*.py")
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    sys.path.insert(0, str(Path.cwd()))
    suite = unittest.defaultTestLoader.discover(args.start, pattern=args.pattern)
    result = unittest.TextTestRunner(verbosity=2, resultclass=JUnitResult).run(suite)
    root = ET.Element("testsuite", tests=str(result.testsRun), failures=str(len(result.failures) + len(result.unexpectedSuccesses)),
                      errors=str(len(result.errors)), skipped=str(len(result.skipped) + len(result.expectedFailures)))
    root.extend(result.cases)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(root).write(args.report, encoding="utf-8", xml_declaration=True)
    return 0 if result.wasSuccessful() and result.testsRun > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
