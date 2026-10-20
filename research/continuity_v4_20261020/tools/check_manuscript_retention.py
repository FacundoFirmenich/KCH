#!/usr/bin/env python3
"""Reconstruct V5 manuscript content from V6 without trusting retention flags.

Usage: python tools/check_manuscript_retention.py --repo REPO --out RECEIPT.json
Only Python's standard library is required. Inputs are never modified. PASS
certifies textual preservation and recorded hashes, not scientific correctness.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys


BASE = Path("research/continuity_v4_20261020")
PAPERS = BASE / "papers"
MAP1 = PAPERS / "PAPER_1_V6_RETENTION_MAP.json"
MAP2 = PAPERS / "RETENTION_EMPIRICAL_V6.json"
ORIGINAL_HASHES = {
    "PAPER1": "c561f4dc0d0dd7259eca0c8be1bcef2c0a10305348805b00491c589dded5cc2b",
    "PAPER2": "2a11ed91da8d1c78050a2500b12982bacf9c0cfb1e39253caa11844776736122",
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


class RetentionCheck:
    def __init__(self, repo, output):
        self.repo = repo.resolve()
        self.output = output.resolve()
        self.checks = 0
        self.inputs = {}

    def require(self, condition, message):
        if not condition:
            raise ValueError(message)
        self.checks += 1

    def read(self, relative):
        relative = Path(relative)
        self.require(not relative.is_absolute(), "Input paths must be relative")
        target = (self.repo / relative).resolve()
        self.require(target.is_relative_to(self.repo), "Input escapes repository")
        self.require(target != self.output, "Receipt must not overwrite an input")
        data = target.read_bytes()
        name = relative.as_posix()
        self.inputs[name] = {"bytes": len(data), "sha256": digest(data)}
        return data

    def load_map(self, path):
        return json.loads(self.read(path).decode("utf-8"))

    def validate_file(self, data, expected_size, expected_hash, label):
        self.require(len(data) == expected_size, label + ": byte count differs")
        self.require(digest(data) == expected_hash, label + ": SHA256 differs")

    def paper1(self):
        record = self.load_map(MAP1)
        source = self.read(record["source_repo_path"])
        final = self.read(record["output_repo_path"])
        self.validate_file(source, record["source_bytes"], record["source_sha256"], "PAPER1 V5")
        self.validate_file(final, record["output_bytes"], record["output_sha256"], "PAPER1 V6")
        self.require(digest(source) == ORIGINAL_HASHES["PAPER1"], "PAPER1 original baseline differs")
        source_text, final_text = source.decode("utf-8"), final.decode("utf-8")
        first_heading = "## 1. Motivation and scope"
        self.require(source_text.count(first_heading) == 1, "PAPER1 ambiguous original body start")
        self.require(final_text.count(first_heading) == 1, "PAPER1 ambiguous final body start")
        source_header, source_body = source_text.split(first_heading, 1)
        source_body = first_heading + source_body
        body = final_text[final_text.index(first_heading):]

        additions = record["additions"]
        identifiers = [item["id"] for item in additions]
        self.require(len(identifiers) == len(set(identifiers)) == 7, "PAPER1 requires seven unique additions")
        begins = re.findall(r"<!-- V6_ADDITION_BEGIN:([A-Z_]+) -->", body)
        ends = re.findall(r"<!-- V6_ADDITION_END:([A-Z_]+) -->", body)
        self.require(sorted(begins) == sorted(ends) == sorted(identifiers), "PAPER1 unmatched/undeclared additions")
        for item in additions:
            identifier = item["id"]
            opening = "<!-- V6_ADDITION_BEGIN:" + identifier + " -->\n"
            closing = "\n<!-- V6_ADDITION_END:" + identifier + " -->"
            matches = list(re.finditer(re.escape(opening) + r"(.*?)" + re.escape(closing), body, re.S))
            self.require(len(matches) == 1, "PAPER1 addition is not unique: " + identifier)
            match = matches[0]
            self.require(digest(match.group(1).encode("utf-8")) == item["sha256"], "PAPER1 addition hash: " + identifier)
            # These delimiters account for the exact insertion whitespace.
            segment = ("\n" + match.group(0) + "\n") if identifier == "REFERENCES" else (match.group(0) + "\n\n")
            self.require(body.count(segment) == 1, "PAPER1 insertion boundary: " + identifier)
            body = body.replace(segment, "", 1)

        changes = record["editorial_transformations"]
        self.require(len(changes) == 7, "PAPER1 requires seven editorial reversals")
        for index, change in reversed(list(enumerate(changes, 1))):
            old, new = change["original"], change["replacement"]
            self.require(bool(old) and bool(new) and old != new, "PAPER1 invalid editorial change")
            self.require(body.count(new) == 1, "PAPER1 reversal is not unique: " + str(index))
            body = body.replace(new, old, 1)
        reconstructed = body.encode("utf-8")
        self.require(reconstructed == source_body.encode("utf-8"), "PAPER1 reconstructed body differs from V5")
        self.require(digest(reconstructed) == record["reconstruction_sha256"], "PAPER1 reconstruction hash differs")
        self.require("<!-- V6_ADDITION_" not in body, "PAPER1 remaining addition marker")

        sections = list(re.finditer(r"^## (?:\d+\.[^\n]*|References)", source_body, re.M))
        retained = record["retained_original_sections"]
        self.require(len(sections) == len(retained) == 18, "PAPER1 section inventory differs")
        for index, (section, item) in enumerate(zip(sections, retained)):
            stop = sections[index + 1].start() if index + 1 < len(sections) else len(source_body)
            content = source_body[section.start():stop].encode("utf-8")
            self.require(section.group(0) == item["heading"], "PAPER1 section heading differs")
            self.validate_file(content, item["original_bytes"], item["original_sha256"], item["heading"])
            self.require(section.group(0) in final_text, "PAPER1 retained heading absent")

        patterns = {
            "display_equation": (r"\\\[.*?\\\]", re.S, 53),
            "fenced_block": (r"```.*?```", re.S, 9),
            "proof": (r"\*\*Proof(?:[^\n]*?)\*\*.*?\\square\\\)", re.S, 9),
            "numbered_statement_heading": (r"^### (?:Theorem|Proposition) \d+[^\n]*", re.M, 9),
        }
        blocks = record["protected_blocks"]
        self.require(len(blocks) == 80, "PAPER1 protected inventory differs")
        self.require(set(item["kind"] for item in blocks) == set(patterns), "PAPER1 unknown protected kind")
        block_counts = {}
        for kind, (pattern, flags, expected) in patterns.items():
            actual = re.findall(pattern, source_text, flags)
            declared = [item for item in blocks if item["kind"] == kind]
            self.require(len(actual) == len(declared) == expected, "PAPER1 protected count: " + kind)
            for index, (content, item) in enumerate(zip(actual, declared), 1):
                self.require(item["index"] == index, "PAPER1 protected index: " + kind)
                encoded = content.encode("utf-8")
                self.validate_file(encoded, item["bytes"], item["sha256"], kind + " " + str(index))
                self.require(encoded in final, "PAPER1 protected block absent: " + kind + " " + str(index))
            block_counts[kind] = len(actual)

        changelog_path = PAPERS / record["original_header_metadata_retained_in"]
        changelog = self.read(changelog_path)
        self.require(bool(source_header), "PAPER1 empty historical header")
        self.require(changelog.count(source_header.encode("utf-8")) == 1, "PAPER1 historical title/status/abstract not retained exactly")
        return {
            "status": "PASS", "source": record["source_repo_path"], "final": record["output_repo_path"],
            "body_reconstructed_byte_exactly": True, "reconstruction_sha256": digest(reconstructed),
            "additions_removed": len(additions), "editorial_changes_reversed": len(changes),
            "sections_verified": len(sections), "protected_blocks_verified": block_counts,
            "historical_header_preserved_exactly_in": changelog_path.as_posix(),
        }

    def paper2(self):
        record = self.load_map(MAP2)
        source, final = self.read(record["source_path"]), self.read(record["v6_path"])
        self.validate_file(source, record["source_bytes"], record["source_sha256"], "PAPER2 V5")
        self.validate_file(final, record["v6_bytes"], record["v6_sha256"], "PAPER2 V6")
        self.require(digest(source) == ORIGINAL_HASHES["PAPER2"], "PAPER2 original baseline differs")
        start, length = record["archive_start_byte"], record["archive_source_bytes"]
        self.require(type(start) is int and type(length) is int and start >= 0, "PAPER2 invalid archive offsets")
        self.require(length == len(source), "PAPER2 archive length differs")
        end = start + length
        self.require(final[start:end] == source, "PAPER2 archival source differs bytewise")
        opening, closing = b"<!-- BEGIN_EXACT_V5_SOURCE -->\n", b"<!-- END_EXACT_V5_SOURCE -->\n"
        self.require(final.count(opening) == final.count(closing) == 1, "PAPER2 archive markers not unique")
        self.require(final[start - len(opening):start] == opening, "PAPER2 archive opening offset differs")
        self.require(final[end:] == closing, "PAPER2 archive closing offset differs")
        self.require(final.count(source) == 1, "PAPER2 original archive is not unique")

        headings = list(re.finditer(rb"^#{1,2} [^\r\n]*", source, re.M))
        sections = record["source_sections"]
        self.require(len(headings) == len(sections) == 14, "PAPER2 requires fourteen sections")
        self.require(headings[0].start() == 0, "PAPER2 partition does not start at zero")
        previous_end = 0
        for index, (heading, item) in enumerate(zip(headings, sections)):
            left = heading.start()
            right = headings[index + 1].start() if index + 1 < len(headings) else len(source)
            self.require(left == previous_end, "PAPER2 partition gap or overlap")
            self.require(item["source_byte_start"] == left and item["source_byte_end_exclusive"] == right, "PAPER2 source section offsets differ")
            self.require(item["v6_byte_start"] == start + left and item["v6_byte_end_exclusive"] == start + right, "PAPER2 final section offsets differ")
            content = source[left:right]
            self.require(digest(content) == item["source_sha256"], "PAPER2 section hash differs")
            self.require(content == final[start + left:start + right], "PAPER2 section differs bytewise")
            self.require(heading.group(0).decode("utf-8") == item["source_heading"], "PAPER2 section heading differs")
            previous_end = right
        self.require(previous_end == len(source), "PAPER2 partition does not cover the full source")
        return {
            "status": "PASS", "source": record["source_path"], "final": record["v6_path"],
            "complete_archive_byte_identical": True, "archive_start_byte": start,
            "archive_end_byte_exclusive": end, "sections_verified": len(sections),
            "section_offsets_form_complete_partition": True,
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True, help="Repository root containing research/")
    parser.add_argument("--out", type=Path, required=True, help="JSON receipt path; never an input file")
    args = parser.parse_args()
    checker = RetentionCheck(args.repo, args.out)
    receipt = {"schema": "manuscript-retention/v1", "status": "FAIL", "papers": {},
               "scope": "Textual preservation and file integrity; not scientific validity or completeness of external literature."}
    try:
        # Keep all receipts away from both manuscript trees, including on failure.
        output = args.out.resolve()
        for protected in (checker.repo / "research/continuity_20261013", checker.repo / PAPERS):
            if output.is_relative_to(protected.resolve()):
                raise ValueError("Receipt path is inside a protected manuscript tree")
        if output == Path(__file__).resolve():
            raise ValueError("Receipt cannot overwrite this checker")
        receipt["papers"]["PAPER1"] = checker.paper1()
        receipt["papers"]["PAPER2"] = checker.paper2()
        receipt["status"] = "PASS"
    except (OSError, ValueError, KeyError, TypeError, IndexError) as error:
        receipt["error"] = str(error)
    receipt["checks_passed"] = checker.checks
    receipt["inputs"] = checker.inputs
    receipt["checker_sha256"] = digest(Path(__file__).read_bytes())
    # A rejected output location must not be written even when reporting failure.
    protected_locations = [checker.repo / "research/continuity_20261013", checker.repo / PAPERS]
    if any(checker.output.is_relative_to(path.resolve()) for path in protected_locations) or checker.output == Path(__file__).resolve():
        print(json.dumps(receipt, indent=2, ensure_ascii=False), file=sys.stderr)
        return 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(receipt["status"] + ": " + str(checker.checks) + " checks; receipt " + str(args.out))
    if receipt["status"] != "PASS":
        print(receipt.get("error", "Retention check failed"), file=sys.stderr)
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
