<!-- chock:hooks:start (compiled by chock -- edit .agents/policies/verify-dependency-exists/) -->
```
on(commit): block(dependency_allowlist) manifests=requirements.txt|pyproject.toml|package.json|... allowlist_file=.chock/dependency-allowlist.txt
Unknown dependency blocked. Verify the package exists in the official registry, then add it to .chock/dependency-allowlist.txt to allow it.
```
<!-- chock:hooks:end -->
