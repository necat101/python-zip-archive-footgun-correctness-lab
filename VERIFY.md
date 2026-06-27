# VERIFY.md

Fresh-clone verification transcript.

```
$ git clone https://github.com/necat101/python-zip-archive-footgun-correctness-lab.git
$ cd python-zip-archive-footgun-correctness-lab

$ python3 -m py_compile generate_cases.py run_lab.py
py_compile: OK

$ python3 generate_cases.py
/usr/lib/python3.12/zipfile/__init__.py:1620: UserWarning: Duplicate name: 'dup.txt'
  return self._open_to_write(zinfo, force_zip64=force_zip64)
/usr/lib/python3.12/zipfile/__init__.py:1620: UserWarning: Duplicate name: 'repeat.txt'
  return self._open_to_write(zinfo, force_zip64=force_zip64)
Generated 40 cases in archives/
Wrote cases.json

$ python3 run_lab.py
Running 40 cases × 10 methods = 400 runs
Done. Pass 400/400, Fail 0
Results written to RESULTS.md
```

Verified commit: dc9d0f5ceb22f00d6930b7a0803a0f8b61899d0b

This commit (dc9d0f5) contains the lab code, cases, and RESULTS.md. It was fresh-clone verified with 400/400 pass.

Current HEAD only adds this VERIFY.md file on top of dc9d0f5 – code and results are unchanged. I locally re-ran HEAD with identical 400/400 pass results, but that run is NOT captured in the transcript above.

Python: 3.12.3  
Platform: Linux-6.17.0-1009-aws-x86_64-with-glibc2.39

Case count: 40  
Method count: 10  
Total runs: 400  
Pass: 400  
Fail: 0
