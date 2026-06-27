# python-zip-archive-footgun-correctness-lab – Results

**Cases:** 40  
**Methods:** 10  
**Total runs:** 400  
**Python:** 3.12.3  
**Platform:** Linux-6.17.0-1009-aws-x86_64-with-glibc2.39  
**zipfile module:** stdlib zipfile  
**Random seed:** 42 (deterministic case generation)  
**Timing method:** time.perf_counter()  
**Memory method:** tracemalloc  
**Compression ratio guard:** 100:1  
**Total uncompressed size guard:** 60000 bytes  
**Member count guard:** 30  
**Subprocess count:** 0  

## Summary

- Pass: 400
- Fail: 0
- CRC-error cases: 2
- Unsafe-path cases: 8
- Duplicate-name cases: 2
- Malformed-archive cases: 1
- Naive-negative cases: 10

## Per-method results

| Method | Pass | Fail | Total |
|--------|------|------|-------|
| zipfile_infolist_baseline | 40 | 0 | 40 |
| zipfile_read_crc_baseline | 40 | 0 | 40 |
| safe_member_path_validator | 40 | 0 | 40 |
| safe_extract_to_tempdir_baseline | 40 | 0 | 40 |
| duplicate_name_detector | 40 | 0 | 40 |
| compression_ratio_guard | 40 | 0 | 40 |
| total_size_and_count_guard | 40 | 0 | 40 |
| prefix_suffix_zip_reader | 40 | 0 | 40 |
| naive_path_join_extractor_dry_run | 40 | 0 | 40 |
| naive_extension_trust_baseline | 40 | 0 | 40 |

## Skip matrix

| Method | Skipped | Reason |
|--------|---------|--------|
| zipfile_infolist_baseline | 0 | – |
| zipfile_read_crc_baseline | 0 | – |
| safe_member_path_validator | 0 | – |
| safe_extract_to_tempdir_baseline | 10 | marked unsafe_to_extract |
| duplicate_name_detector | 0 | – |
| compression_ratio_guard | 0 | – |
| total_size_and_count_guard | 0 | – |
| prefix_suffix_zip_reader | 0 | – |
| naive_path_join_extractor_dry_run | 0 | – |
| naive_extension_trust_baseline | 0 | – |

## Case catalog

| Case | Category | Members | Uncomp bytes | Archive bytes | Unsafe? | Dup? | CRC OK? | Tags |
|------|----------|---------|--------------|---------------|---------|------|---------|------|
| c01_normal | normal | 1 | 3 | 121 | n | n | Y | normal |
| c02_nested | directory | 1 | 7 | 139 | n | n | Y | directory, normal |
| c03_empty_dir | directory | 1 | 0 | 116 | n | n | Y | directory, empty_dir |
| c04_multi | normal | 5 | 25 | 527 | n | n | Y | normal, multi |
| c05_stored | compression | 1 | 11 | 127 | n | n | Y | compression, stored |
| c06_deflated | compression | 1 | 150 | 128 | n | n | Y | compression, deflated |
| c07_archive_comment | compression | 1 | 1 | 129 | n | n | Y | compression, archive_comment |
| c09_unicode | unicode_name | 1 | 7 | 159 | n | n | Y | unicode_name |
| c10_spaces | unicode_name | 1 | 2 | 150 | n | n | Y | unicode_name, spaces |
| c11_backslash | path_separator | 1 | 2 | 132 | Y | n | Y | path_separator, windows_path |
| c12_fwdslash | path_separator | 1 | 2 | 132 | n | n | Y | path_separator, normal |
| c13_abs | absolute_path | 1 | 2 | 124 | Y | n | Y | absolute_path, traversal, naive_negative |
| c14_dotdot | traversal | 1 | 2 | 124 | Y | n | Y | traversal, naive_negative |
| c15_dotdot2 | traversal | 1 | 1 | 133 | Y | n | Y | traversal, naive_negative |
| c16_win_drive | windows_path | 1 | 1 | 133 | Y | n | Y | windows_path, absolute_path, naive_negative |
| c17_win_bs_traversal | windows_path | 1 | 1 | 123 | Y | n | Y | windows_path, traversal |
| c18_duplicate | duplicate_name | 2 | 11 | 213 | n | Y | Y | duplicate_name, naive_negative |
| c19_duplicate3 | duplicate_name | 3 | 3 | 313 | n | Y | Y | duplicate_name |
| c20_crc_mismatch | crc_error | 1 | 18 | 132 | n | n | n | crc_error, naive_negative |
| c21_malformed | malformed_zip | 0 | 0 | 37 | n | n | n | malformed_zip, naive_negative |
| c22_prefix | prefix_suffix | 1 | 2 | 135 | n | n | Y | prefix_suffix |
| c23_suffix | prefix_suffix | 1 | 2 | 135 | n | n | Y | prefix_suffix |
| c24_concat | prefix_suffix | 1 | 1 | 218 | n | n | Y | prefix_suffix |
| c25_bomb_caveat | zip_bomb_caveat | 1 | 50000 | 181 | n | n | Y | zip_bomb_caveat |
| c26_many_files | zip_bomb_caveat | 40 | 40 | 3722 | n | n | Y | zip_bomb_caveat |
| c27_big_uncomp | zip_bomb_caveat | 1 | 80000 | 80112 | n | n | Y | zip_bomb_caveat |
| c28_unsupported_comp | compression | 1 | 2 | 110 | n | n | Y | compression |
| c29_symlink_attr | symlink_caveat | 1 | 6 | 120 | n | n | Y | symlink_caveat |
| c30_executable | extension_caveat | 1 | 6 | 124 | n | n | Y | extension_caveat |
| c31_ext_trust | extension_caveat | 1 | 9 | 131 | n | n | Y | extension_caveat, naive_negative |
| c32_double_ext | extension_caveat | 1 | 1 | 133 | n | n | Y | extension_caveat, naive_negative |
| c34_normal2 | normal | 1 | 5 | 123 | n | n | Y | normal |
| c35_safe_subdir | directory | 1 | 2 | 136 | n | n | Y | directory, normal |
| c36_dot_slash | path_separator | 1 | 1 | 121 | n | n | Y | path_separator |
| c37_double_slash | path_separator | 1 | 1 | 117 | n | n | Y | path_separator |
| c38_dir_plus_file | directory | 2 | 1 | 207 | n | n | Y | directory |
| c39_dotfile | normal | 1 | 1 | 115 | n | n | Y | normal |
| c40_empty_file | normal | 1 | 0 | 116 | n | n | Y | normal |
| c41_mixed_sep | traversal | 1 | 1 | 127 | Y | n | Y | traversal, naive_negative |
| c42_win_abs_bs | windows_path | 1 | 1 | 139 | Y | n | Y | windows_path |

## Method details

### zipfile_infolist_baseline

Pass: 40/40

### zipfile_read_crc_baseline

Pass: 40/40

### safe_member_path_validator

Pass: 40/40

### safe_extract_to_tempdir_baseline

Pass: 40/40

### duplicate_name_detector

Pass: 40/40

### compression_ratio_guard

Pass: 40/40

### total_size_and_count_guard

Pass: 40/40

### prefix_suffix_zip_reader

Pass: 40/40

### naive_path_join_extractor_dry_run

Pass: 40/40

### naive_extension_trust_baseline

Pass: 40/40

## Observations

- `zipfile.infolist_baseline` correctly enumerates central-directory entries, including duplicate filenames.
- `zipfile_read_crc_baseline` catches CRC mismatches and malformed archives as expected.
- `safe_member_path_validator` detects ../ traversal, absolute paths, Windows drive paths, and backslash-traversal cases.
- `safe_extract_to_tempdir_baseline` only extracts paths that pass containment checks, in a temporary directory.
- `duplicate_name_detector` finds repeated member names in the central directory.
- `compression_ratio_guard` flags toy high-compression-ratio archives (zip-bomb caveat).
- `total_size_and_count_guard` rejects archives exceeding toy thresholds.
- `prefix_suffix_zip_reader` confirms Python zipfile accepts prefix/suffix bytes.
- `naive_path_join_extractor_dry_run` (dry-run only) would extract unsafe paths – that's the footgun.
- `naive_extension_trust_baseline` trusts extensions, missing path traversal, duplicates, CRC errors, etc.

## Conclusion

ZIP is widely supported and useful, but safe extraction requires path containment checks, duplicate-name handling as a policy decision, CRC validation, and compression/size guards. Blindly joining paths or trusting extensions is unsafe. This is a toy lab – not a production archive scanner.

## Reproduction

```
python3 -m py_compile generate_cases.py run_lab.py
python3 generate_cases.py
python3 run_lab.py
```
