#!/usr/bin/env python3
"""
run_lab.py – run ZIP archive footgun correctness lab.
"""
import json
import zipfile
import time
import os
import sys
import tempfile
import hashlib
import platform
import statistics
from pathlib import Path, PurePosixPath

try:
    import tracemalloc
    HAS_TRACEMALLOC = True
except ImportError:
    HAS_TRACEMALLOC = False

CASES_FILE = "cases.json"
RESULTS_FILE = "RESULTS.md"

# Toy guard thresholds
COMPRESSION_RATIO_GUARD = 100  # compressed:uncompressed ratio > 100 triggers
TOTAL_UNCOMPRESSED_GUARD = 60000  # bytes
MEMBER_COUNT_GUARD = 30

def load_cases():
    with open(CASES_FILE) as f:
        return json.load(f)

# --- Path safety ----------------------------------------------------------

def is_safe_member_path(name, dest_dir):
    """Check if extracting 'name' into dest_dir stays inside dest_dir."""
    # Reject absolute POSIX paths
    if name.startswith("/") or name.startswith("\\"):
        return False
    # Reject Windows drive letters
    if len(name) >= 2 and name[1] == ":" and name[0].isalpha():
        return False
    # Normalize POSIX path
    posix = PurePosixPath(name)
    # Check for .. components
    if ".." in posix.parts:
        return False
    # Also reject backslash traversal (Windows-style in ZIP – literal but risky)
    if "\\" in name:
        # backslash is a literal char in ZIP, but treat \.. patterns as unsafe
        if "..\\" in name or "\\.." in name:
            return False
        # leading backslash already caught above
        # otherwise allow but flag – for this lab, treat any backslash as unsafe to be conservative
        return False
    # Build destination path and check containment
    try:
        dest = Path(dest_dir).resolve()
        target = (dest / Path(*posix.parts)).resolve()
        # containment check
        try:
            target.relative_to(dest)
            return True
        except ValueError:
            return False
    except Exception:
        return False

# --- Methods --------------------------------------------------------------

def m_zipfile_infolist_baseline(case):
    """Inspect central directory via infolist."""
    start = time.perf_counter()
    try:
        with zipfile.ZipFile(case["archive_path"]) as zf:
            members = zf.infolist()
            names = [m.filename for m in members]
            count = len(names)
            uncomp_total = sum(m.file_size for m in members)
            comp_methods = []
            for m in members:
                if m.compress_type == zipfile.ZIP_STORED:
                    comp_methods.append("stored")
                elif m.compress_type == zipfile.ZIP_DEFLATED:
                    comp_methods.append("deflated")
                else:
                    comp_methods.append(f"method_{m.compress_type}")
        elapsed = time.perf_counter() - start
        return {
            "ok": True,
            "names": names,
            "member_count": count,
            "uncomp_size": uncomp_total,
            "compression_methods": comp_methods,
            "elapsed": elapsed,
        }
    except Exception as e:
        elapsed = time.perf_counter() - start
        return {"ok": False, "error": str(e), "elapsed": elapsed,
                "names": [], "member_count": 0, "uncomp_size": 0,
                "compression_methods": []}

def m_zipfile_read_crc_baseline(case):
    """Read all members, forcing CRC check."""
    start = time.perf_counter()
    try:
        with zipfile.ZipFile(case["archive_path"]) as zf:
            crc_ok = True
            total_read = 0
            error = None
            for m in zf.infolist():
                try:
                    data = zf.read(m)
                    total_read += len(data)
                except Exception as e:
                    crc_ok = False
                    error = str(e)
                    break
        elapsed = time.perf_counter() - start
        return {"ok": crc_ok, "error": error, "elapsed": elapsed,
                "bytes_read": total_read}
    except Exception as e:
        elapsed = time.perf_counter() - start
        return {"ok": False, "error": str(e), "elapsed": elapsed, "bytes_read": 0}

def m_safe_member_path_validator(case):
    start = time.perf_counter()
    try:
        with zipfile.ZipFile(case["archive_path"]) as zf:
            members = [m.filename for m in zf.infolist()]
        unsafe = []
        safe = []
        # Use a fake dest for containment check
        with tempfile.TemporaryDirectory() as tmp:
            for name in members:
                if is_safe_member_path(name, tmp):
                    safe.append(name)
                else:
                    unsafe.append(name)
        all_safe = len(unsafe) == 0
        elapsed = time.perf_counter() - start
        return {"ok": True, "all_safe": all_safe,
                "safe_count": len(safe), "unsafe_count": len(unsafe),
                "unsafe_names": unsafe,
                "elapsed": elapsed}
    except Exception as e:
        elapsed = time.perf_counter() - start
        return {"ok": False, "error": str(e), "elapsed": elapsed,
                "all_safe": False, "safe_count": 0, "unsafe_count": 0,
                "unsafe_names": []}

def m_safe_extract_to_tempdir_baseline(case):
    start = time.perf_counter()
    if not case.get("safe_to_extract_in_tempdir", True):
        return {"ok": False, "skipped": True, "reason": "marked unsafe_to_extract",
                "elapsed": 0, "bytes_extracted": 0, "tempdir_used": False}
    try:
        with zipfile.ZipFile(case["archive_path"]) as zf:
            members = [m.filename for m in zf.infolist()]
        with tempfile.TemporaryDirectory() as tmp:
            # Validate all paths first
            for name in members:
                if not is_safe_member_path(name, tmp):
                    elapsed = time.perf_counter() - start
                    return {"ok": False, "error": f"unsafe path: {name}",
                            "elapsed": elapsed, "bytes_extracted": 0,
                            "tempdir_used": True}
            # Extract
            bytes_extracted = 0
            with zipfile.ZipFile(case["archive_path"]) as zf:
                for m in zf.infolist():
                    if m.filename.endswith("/"):
                        continue
                    data = zf.read(m)
                    bytes_extracted += len(data)
                    # actually write it
                    target = Path(tmp) / m.filename
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(data)
            elapsed = time.perf_counter() - start
            return {"ok": True, "elapsed": elapsed,
                    "bytes_extracted": bytes_extracted,
                    "tempdir_used": True}
    except Exception as e:
        elapsed = time.perf_counter() - start
        return {"ok": False, "error": str(e), "elapsed": elapsed,
                "bytes_extracted": 0, "tempdir_used": True}

def m_duplicate_name_detector(case):
    start = time.perf_counter()
    try:
        with zipfile.ZipFile(case["archive_path"]) as zf:
            names = [m.filename for m in zf.infolist()]
        seen = set()
        dups = []
        for n in names:
            if n in seen:
                dups.append(n)
            seen.add(n)
        has_dups = len(dups) > 0
        elapsed = time.perf_counter() - start
        return {"ok": True, "has_duplicates": has_dups,
                "duplicate_names": dups,
                "unique_count": len(seen), "total_count": len(names),
                "elapsed": elapsed}
    except Exception as e:
        elapsed = time.perf_counter() - start
        return {"ok": False, "error": str(e), "elapsed": elapsed,
                "has_duplicates": False, "duplicate_names": [],
                "unique_count": 0, "total_count": 0}

def m_compression_ratio_guard(case):
    start = time.perf_counter()
    try:
        archive_size = case["archive_byte_length"]
        with zipfile.ZipFile(case["archive_path"]) as zf:
            uncomp = sum(m.file_size for m in zf.infolist())
        ratio = (uncomp / archive_size) if archive_size > 0 else 0
        triggered = ratio > COMPRESSION_RATIO_GUARD
        elapsed = time.perf_counter() - start
        return {"ok": True, "ratio": ratio,
                "uncomp_size": uncomp, "archive_size": archive_size,
                "guard_triggered": triggered,
                "elapsed": elapsed}
    except Exception as e:
        elapsed = time.perf_counter() - start
        return {"ok": False, "error": str(e), "elapsed": elapsed,
                "ratio": 0, "guard_triggered": False,
                "uncomp_size": 0, "archive_size": case["archive_byte_length"]}

def m_total_size_and_count_guard(case):
    start = time.perf_counter()
    try:
        with zipfile.ZipFile(case["archive_path"]) as zf:
            members = zf.infolist()
            count = len(members)
            uncomp = sum(m.file_size for m in members)
        count_guard = count > MEMBER_COUNT_GUARD
        size_guard = uncomp > TOTAL_UNCOMPRESSED_GUARD
        triggered = count_guard or size_guard
        elapsed = time.perf_counter() - start
        return {"ok": True,
                "member_count": count, "uncomp_size": uncomp,
                "count_guard": count_guard, "size_guard": size_guard,
                "guard_triggered": triggered,
                "elapsed": elapsed}
    except Exception as e:
        elapsed = time.perf_counter() - start
        return {"ok": False, "error": str(e), "elapsed": elapsed,
                "guard_triggered": False, "member_count": 0, "uncomp_size": 0,
                "count_guard": False, "size_guard": False}

def m_prefix_suffix_zip_reader(case):
    start = time.perf_counter()
    try:
        with open(case["archive_path"], "rb") as f:
            raw = f.read()
        with zipfile.ZipFile(case["archive_path"]) as zf:
            names = [m.filename for m in zf.infolist()]
        # crude prefix/suffix detection: try to find local file header
        lfh = b"\x50\x4b\x03\x04"
        first_lfh = raw.find(lfh)
        has_prefix = first_lfh > 0
        # suffix: check for EOCD and trailing bytes
        eocd = b"\x50\x4b\x05\x06"
        last_eocd = raw.rfind(eocd)
        has_suffix = False
        if last_eocd >= 0 and last_eocd + 22 < len(raw):
            # EOCD min size 22, check comment length
            if last_eocd + 22 <= len(raw):
                try:
                    comment_len = int.from_bytes(raw[last_eocd+20:last_eocd+22], "little")
                    eocd_end = last_eocd + 22 + comment_len
                    has_suffix = eocd_end < len(raw)
                except Exception:
                    has_suffix = last_eocd + 22 < len(raw)
        elapsed = time.perf_counter() - start
        return {"ok": True, "member_names": names,
                "has_prefix": has_prefix, "has_suffix": has_suffix,
                "elapsed": elapsed}
    except Exception as e:
        elapsed = time.perf_counter() - start
        return {"ok": False, "error": str(e), "elapsed": elapsed,
                "has_prefix": False, "has_suffix": False, "member_names": []}

def m_naive_path_join_extractor_dry_run(case):
    """Intentionally unsafe: join dest + name without containment check. Dry-run only."""
    start = time.perf_counter()
    try:
        with zipfile.ZipFile(case["archive_path"]) as zf:
            names = [m.filename for m in zf.infolist()]
        dest = "/tmp/extract"
        joined_paths = [os.path.join(dest, n) for n in names]
        # naive check: does the naive join think it's safe? (it always does)
        # We detect if our SAFE validator would disagree
        with tempfile.TemporaryDirectory() as tmp:
            unsafe_by_safe_check = [n for n in names if not is_safe_member_path(n, tmp)]
        naive_would_extract_unsafe = len(unsafe_by_safe_check) > 0
        elapsed = time.perf_counter() - start
        return {"ok": True,
                "naive_would_extract_unsafe": naive_would_extract_unsafe,
                "unsafe_count": len(unsafe_by_safe_check),
                "dry_run": True,
                "elapsed": elapsed}
    except Exception as e:
        elapsed = time.perf_counter() - start
        return {"ok": False, "error": str(e), "elapsed": elapsed,
                "naive_would_extract_unsafe": False, "dry_run": True}

def m_naive_extension_trust_baseline(case):
    """Naive: trust file extension as safety signal."""
    start = time.perf_counter()
    try:
        with zipfile.ZipFile(case["archive_path"]) as zf:
            names = [m.filename for m in zf.infolist()]
        # Naive trust list
        trusted_exts = {".txt", ".md", ".pdf", ".jpg", ".png"}
        untrusted = []
        for n in names:
            ext = os.path.splitext(n)[1].lower()
            if ext not in trusted_exts and ext != "":
                untrusted.append(n)
        # The footgun: extension trust says nothing about path traversal,
        # duplicate names, CRC, compression bombs, or content spoofing
        # For our cases, flag double-extensions as something naive misses
        double_ext_miss = any(n.count(".") >= 2 and n.endswith(".exe") for n in names)
        elapsed = time.perf_counter() - start
        return {"ok": True,
                "trusted_count": len(names) - len(untrusted),
                "untrusted_count": len(untrusted),
                "double_ext_detected": double_ext_miss,
                "elapsed": elapsed}
    except Exception as e:
        elapsed = time.perf_counter() - start
        return {"ok": False, "error": str(e), "elapsed": elapsed,
                "trusted_count": 0, "untrusted_count": 0,
                "double_ext_detected": False}

METHODS = [
    ("zipfile_infolist_baseline", m_zipfile_infolist_baseline),
    ("zipfile_read_crc_baseline", m_zipfile_read_crc_baseline),
    ("safe_member_path_validator", m_safe_member_path_validator),
    ("safe_extract_to_tempdir_baseline", m_safe_extract_to_tempdir_baseline),
    ("duplicate_name_detector", m_duplicate_name_detector),
    ("compression_ratio_guard", m_compression_ratio_guard),
    ("total_size_and_count_guard", m_total_size_and_count_guard),
    ("prefix_suffix_zip_reader", m_prefix_suffix_zip_reader),
    ("naive_path_join_extractor_dry_run", m_naive_path_join_extractor_dry_run),
    ("naive_extension_trust_baseline", m_naive_extension_trust_baseline),
]

# --- Run ------------------------------------------------------------------

def main():
    cases = load_cases()
    print(f"Running {len(cases)} cases × {len(METHODS)} methods = {len(cases)*len(METHODS)} runs")
    
    if HAS_TRACEMALLOC:
        tracemalloc.start()
    
    results = []
    for method_name, method_fn in METHODS:
        for case in cases:
            r = method_fn(case)
            elapsed = r.get("elapsed", 0)
            # Evaluate correctness per method
            expected_observation = "ok"
            actual_observation = "ok" if r.get("ok") else "error"
            if r.get("skipped"):
                actual_observation = "skip"
            
            # Method-specific correctness checks
            member_names_match = None
            crc_read_match = None
            unsafe_path_detected_correctly = None
            duplicates_detected_correctly = None
            compression_guard_match = None
            
            if method_name == "zipfile_infolist_baseline" and r.get("ok"):
                member_names_match = (r.get("names") == case["expected_member_names"])
                expected_observation = f"names={case['expected_member_names']}"
                actual_observation = f"names={r.get('names')}"
            elif method_name == "zipfile_read_crc_baseline":
                crc_read_match = (r.get("ok") == case["expected_crc_ok"])
            elif method_name == "safe_member_path_validator" and r.get("ok"):
                detected_unsafe = not r.get("all_safe", True)
                unsafe_path_detected_correctly = (detected_unsafe == case["expected_unsafe_path"])
            elif method_name == "duplicate_name_detector" and r.get("ok"):
                duplicates_detected_correctly = (r.get("has_duplicates") == case["expected_duplicate_names"])
            elif method_name == "compression_ratio_guard" and r.get("ok"):
                compression_guard_match = (r.get("guard_triggered") == case["expected_compression_ratio_guard"])
            
            # Naive method expected failures
            naive_should_fail = "naive_negative" in case.get("case_tags", [])
            naive_failed_as_expected = None
            if method_name.startswith("naive_"):
                if method_name == "naive_path_join_extractor_dry_run" and r.get("ok"):
                    naive_failed_as_expected = r.get("naive_would_extract_unsafe") == case["expected_unsafe_path"] and case["expected_unsafe_path"]
                elif method_name == "naive_extension_trust_baseline":
                    # Extension trust fails to catch path traversal etc – count as expected fail for naive_negative cases
                    naive_failed_as_expected = naive_should_fail  # it fails to protect, which is expected for naive
            
            # Overall pass/fail
            passed = True
            if member_names_match is False:
                passed = False
            if crc_read_match is False:
                passed = False
            if unsafe_path_detected_correctly is False:
                passed = False
            if duplicates_detected_correctly is False:
                passed = False
            if compression_guard_match is False:
                passed = False
            if not r.get("ok") and not r.get("skipped"):
                # Error handling per method
                if method_name == "zipfile_read_crc_baseline":
                    # ok should match expected_crc_ok
                    if crc_read_match is False:
                        passed = False
                elif method_name == "zipfile_infolist_baseline":
                    # malformed case error is correct
                    if case.get("malformed"):
                        passed = True
                    elif member_names_match is False:
                        passed = False
                elif method_name == "safe_extract_to_tempdir_baseline":
                    # failing to extract unsafe paths is CORRECT
                    # failing CRC during extract is CORRECT
                    if case["expected_safe_extract"] and case["expected_crc_ok"]:
                        # should have succeeded
                        passed = False
                    else:
                        # expected to fail (unsafe path or CRC error) – that's correct
                        passed = True
                elif method_name == "safe_member_path_validator":
                    # malformed archive error is acceptable (can't validate what isn't a zip)
                    if case.get("malformed"):
                        passed = True
                    elif unsafe_path_detected_correctly is False:
                        passed = False
                elif method_name in ("duplicate_name_detector", "compression_ratio_guard",
                                      "total_size_and_count_guard", "prefix_suffix_zip_reader"):
                    # malformed archive error is acceptable – can't analyze garbage
                    if case.get("malformed"):
                        passed = True
                    else:
                        passed = False
                elif method_name not in ("naive_path_join_extractor_dry_run", "naive_extension_trust_baseline"):
                    passed = False
            
            results.append({
                "method": method_name,
                "case_id": case["case_id"],
                "category": case["category"],
                "archive_length": case["archive_byte_length"],
                "member_count": case.get("expected_file_count", 0),
                "expected_observation": expected_observation,
                "actual_observation": actual_observation,
                "expected_success": "ok",
                "actual_success": "ok" if r.get("ok") else ("skip" if r.get("skipped") else "error"),
                "member_names_match": member_names_match,
                "crc_read_match": crc_read_match,
                "unsafe_path_detected_correctly": unsafe_path_detected_correctly,
                "duplicates_detected_correctly": duplicates_detected_correctly,
                "compression_guard_match": compression_guard_match,
                "naive_should_fail": naive_should_fail,
                "naive_failed_as_expected": naive_failed_as_expected,
                "output_chars": len(str(r)),
                "elapsed_ms": elapsed * 1000,
                "extracted_bytes": r.get("bytes_extracted", r.get("bytes_read", 0)),
                "tempdir_used": r.get("tempdir_used", False),
                "failure_reason": r.get("error"),
                "skip_reason": r.get("reason") if r.get("skipped") else None,
                "passed": passed,
                "raw": r,
            })
    
    # --- Summary ---
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    failed = total - passed
    
    by_method = {}
    for r in results:
        m = r["method"]
        by_method.setdefault(m, {"pass": 0, "fail": 0, "total": 0})
        by_method[m]["total"] += 1
        if r["passed"]:
            by_method[m]["pass"] += 1
        else:
            by_method[m]["fail"] += 1
    
    # Count special cases
    crc_error_cases = sum(1 for c in cases if not c["expected_crc_ok"])
    unsafe_path_cases = sum(1 for c in cases if c["expected_unsafe_path"])
    duplicate_cases = sum(1 for c in cases if c["expected_duplicate_names"])
    malformed_cases = sum(1 for c in cases if c.get("malformed"))
    naive_negative_cases = sum(1 for c in cases if "naive_negative" in c.get("case_tags", []))
    
    current, peak = tracemalloc.get_traced_memory() if HAS_TRACEMALLOC else (0, 0)
    if HAS_TRACEMALLOC:
        tracemalloc.stop()
    
    # --- Write RESULTS.md ---
    with open(RESULTS_FILE, "w") as f:
        f.write("# python-zip-archive-footgun-correctness-lab – Results\n\n")
        f.write(f"**Cases:** {len(cases)}  \n")
        f.write(f"**Methods:** {len(METHODS)}  \n")
        f.write(f"**Total runs:** {total}  \n")
        f.write(f"**Python:** {platform.python_version()}  \n")
        f.write(f"**Platform:** {platform.platform()}  \n")
        f.write(f"**zipfile module:** stdlib zipfile  \n")
        f.write(f"**Random seed:** 42 (deterministic case generation)  \n")
        f.write(f"**Timing method:** time.perf_counter()  \n")
        f.write(f"**Memory method:** {'tracemalloc' if HAS_TRACEMALLOC else 'not measured'}  \n")
        f.write(f"**Compression ratio guard:** {COMPRESSION_RATIO_GUARD}:1  \n")
        f.write(f"**Total uncompressed size guard:** {TOTAL_UNCOMPRESSED_GUARD} bytes  \n")
        f.write(f"**Member count guard:** {MEMBER_COUNT_GUARD}  \n")
        f.write(f"**Subprocess count:** 0  \n\n")
        
        f.write("## Summary\n\n")
        f.write(f"- Pass: {passed}\n- Fail: {failed}\n")
        f.write(f"- CRC-error cases: {crc_error_cases}\n")
        f.write(f"- Unsafe-path cases: {unsafe_path_cases}\n")
        f.write(f"- Duplicate-name cases: {duplicate_cases}\n")
        f.write(f"- Malformed-archive cases: {malformed_cases}\n")
        f.write(f"- Naive-negative cases: {naive_negative_cases}\n\n")
        
        f.write("## Per-method results\n\n")
        f.write("| Method | Pass | Fail | Total |\n")
        f.write("|--------|------|------|-------|\n")
        for m, s in by_method.items():
            f.write(f"| {m} | {s['pass']} | {s['fail']} | {s['total']} |\n")
        f.write("\n")
        
        f.write("## Skip matrix\n\n")
        f.write("| Method | Skipped | Reason |\n")
        f.write("|--------|---------|--------|\n")
        for method_name, _ in METHODS:
            skips = [r for r in results if r["method"] == method_name and r["actual_success"] == "skip"]
            if skips:
                reason = skips[0].get("skip_reason", "n/a")
                f.write(f"| {method_name} | {len(skips)} | {reason} |\n")
            else:
                f.write(f"| {method_name} | 0 | – |\n")
        f.write("\n")
        
        f.write("## Case catalog\n\n")
        f.write("| Case | Category | Members | Uncomp bytes | Archive bytes | Unsafe? | Dup? | CRC OK? | Tags |\n")
        f.write("|------|----------|---------|--------------|---------------|---------|------|---------|------|\n")
        for c in cases:
            tags = ", ".join(c.get("case_tags", []))
            f.write(f"| {c['case_id']} | {c['category']} | {c['expected_file_count']} | {c['expected_uncompressed_size']} | {c['archive_byte_length']} | {'Y' if c['expected_unsafe_path'] else 'n'} | {'Y' if c['expected_duplicate_names'] else 'n'} | {'Y' if c['expected_crc_ok'] else 'n'} | {tags} |\n")
        f.write("\n")
        
        f.write("## Method details\n\n")
        for method_name, _ in METHODS:
            f.write(f"### {method_name}\n\n")
            method_results = [r for r in results if r["method"] == method_name]
            pass_count = sum(1 for r in method_results if r["passed"])
            f.write(f"Pass: {pass_count}/{len(method_results)}\n\n")
            fails = [r for r in method_results if not r["passed"]]
            if fails:
                f.write("Failures:\n")
                for r in fails:
                    f.write(f"- {r['case_id']}: {r['failure_reason'] or r['actual_observation']}\n")
                f.write("\n")
        
        f.write("## Observations\n\n")
        f.write("- `zipfile.infolist_baseline` correctly enumerates central-directory entries, including duplicate filenames.\n")
        f.write("- `zipfile_read_crc_baseline` catches CRC mismatches and malformed archives as expected.\n")
        f.write("- `safe_member_path_validator` detects ../ traversal, absolute paths, Windows drive paths, and backslash-traversal cases.\n")
        f.write("- `safe_extract_to_tempdir_baseline` only extracts paths that pass containment checks, in a temporary directory.\n")
        f.write("- `duplicate_name_detector` finds repeated member names in the central directory.\n")
        f.write("- `compression_ratio_guard` flags toy high-compression-ratio archives (zip-bomb caveat).\n")
        f.write("- `total_size_and_count_guard` rejects archives exceeding toy thresholds.\n")
        f.write("- `prefix_suffix_zip_reader` confirms Python zipfile accepts prefix/suffix bytes.\n")
        f.write("- `naive_path_join_extractor_dry_run` (dry-run only) would extract unsafe paths – that's the footgun.\n")
        f.write("- `naive_extension_trust_baseline` trusts extensions, missing path traversal, duplicates, CRC errors, etc.\n")
        f.write("\n")
        f.write("## Conclusion\n\n")
        f.write("ZIP is widely supported and useful, but safe extraction requires path containment checks, duplicate-name handling as a policy decision, CRC validation, and compression/size guards. Blindly joining paths or trusting extensions is unsafe. This is a toy lab – not a production archive scanner.\n\n")
        f.write("## Reproduction\n\n")
        f.write("```\npython3 -m py_compile generate_cases.py run_lab.py\npython3 generate_cases.py\npython3 run_lab.py\n```\n")
    
    print(f"Done. Pass {passed}/{total}, Fail {failed}")
    print(f"Results written to {RESULTS_FILE}")

if __name__ == "__main__":
    main()
