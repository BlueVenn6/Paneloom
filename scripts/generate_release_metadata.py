from __future__ import annotations

import argparse
import importlib.metadata as metadata
import json
import re
import subprocess
import uuid
from collections import Counter, deque
from datetime import datetime
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


MIT_TEXT = """MIT License

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

CLASSIFIER_LICENSES = {
    "License :: OSI Approved :: Apache Software License": "Apache-2.0",
    "License :: OSI Approved :: BSD License": "BSD-3-Clause",
    "License :: OSI Approved :: MIT License": "MIT",
    "License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)": "MPL-2.0",
    "License :: OSI Approved :: Python Software Foundation License": "PSF-2.0",
}


def _git(root: Path, *arguments: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(root), *arguments],
        text=True,
        encoding="utf-8",
    ).strip()


def _requirement_roots(path: Path, seen: set[Path] | None = None) -> set[str]:
    resolved = path.resolve()
    seen = seen or set()
    if resolved in seen:
        return set()
    seen.add(resolved)
    names: set[str] = set()
    for raw_line in resolved.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        include = re.match(r"^(?:-r|--requirement)\s+(.+)$", line)
        if include:
            names.update(_requirement_roots(resolved.parent / include.group(1), seen))
            continue
        names.add(canonicalize_name(Requirement(line).name))
    return names


def _installed_distributions() -> dict[str, metadata.Distribution]:
    return {
        canonicalize_name(dist.metadata["Name"]): dist
        for dist in metadata.distributions()
        if dist.metadata.get("Name")
    }


def _dependency_closure(
    direct_names: set[str],
    installed: dict[str, metadata.Distribution],
) -> tuple[set[str], dict[str, set[str]]]:
    queue = deque(sorted(direct_names))
    included: set[str] = set()
    edges: dict[str, set[str]] = {}
    while queue:
        name = queue.popleft()
        if name in included:
            continue
        dist = installed.get(name)
        if dist is None:
            raise RuntimeError(f"Required distribution is not installed: {name}")
        included.add(name)
        dependencies: set[str] = set()
        for requirement_text in dist.requires or []:
            requirement = Requirement(requirement_text)
            if requirement.marker and not requirement.marker.evaluate({"extra": ""}):
                continue
            dependency = canonicalize_name(requirement.name)
            if dependency not in installed:
                raise RuntimeError(f"Dependency of {name} is not installed: {dependency}")
            dependencies.add(dependency)
            if dependency not in included:
                queue.append(dependency)
        edges[name] = dependencies
    return included, edges


def _license_files(dist: metadata.Distribution) -> list[Path]:
    paths = []
    for entry in dist.files or []:
        lowered = str(entry).lower()
        if any(token in lowered for token in ("license", "copying", "notice")):
            path = Path(dist.locate_file(entry))
            if path.is_file() and path not in paths:
                paths.append(path)
    return paths


def _license_expression(dist: metadata.Distribution) -> str:
    expression = (dist.metadata.get("License-Expression") or "").strip()
    if expression:
        return expression
    declared = (dist.metadata.get("License") or "").strip()
    lowered = declared.lower()
    if declared and len(declared) < 100 and "\n" not in declared:
        if "gplv2-or-later" in lowered and "special exception" in lowered:
            return "GPL-2.0-or-later WITH Bootloader-exception"
        aliases = {
            "apache 2.0": "Apache-2.0",
            "apache-2.0": "Apache-2.0",
            "bsd": "BSD-3-Clause",
            "bsd-3-clause": "BSD-3-Clause",
            "isc": "ISC",
            "mit": "MIT",
            "mpl-2.0": "MPL-2.0",
        }
        if lowered in aliases:
            return aliases[lowered]
    for classifier in dist.metadata.get_all("Classifier") or []:
        if classifier in CLASSIFIER_LICENSES:
            return CLASSIFIER_LICENSES[classifier]
    license_text = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")[:500]
        for path in _license_files(dist)
    ).lower()
    if "mit license" in license_text or "permission is hereby granted" in license_text:
        return "MIT"
    if "apache license" in license_text and "version 2.0" in license_text:
        return "Apache-2.0"
    if "mozilla public license" in license_text:
        return "MPL-2.0"
    if "redistribution and use in source and binary forms" in license_text:
        return "BSD-3-Clause"
    if "gnu general public license" in license_text and "special exception" in lowered:
        return "GPL-2.0-or-later WITH Bootloader-exception"
    return "UNKNOWN"


def _purl(name: str, version: str) -> str:
    return f"pkg:pypi/{canonicalize_name(name)}@{version}"


def _python_bom(
    root: Path,
    version: str,
    commit: str,
    scope: str,
    names: set[str],
    direct_names: set[str],
    edges: dict[str, set[str]],
    installed: dict[str, metadata.Distribution],
    source_identity: dict,
) -> dict:
    components = []
    for name in sorted(names):
        dist = installed[name]
        dist_name = dist.metadata["Name"]
        dist_version = dist.version
        expression = _license_expression(dist)
        if expression == "UNKNOWN":
            raise RuntimeError(f"Unknown Python license: {dist_name} {dist_version}")
        component = {
            "type": "library",
            "bom-ref": _purl(dist_name, dist_version),
            "name": dist_name,
            "version": dist_version,
            "purl": _purl(dist_name, dist_version),
            "licenses": [{"license": {"id": expression}}],
            "properties": [
                {
                    "name": "paneloom:dependency-kind",
                    "value": "direct" if name in direct_names else "transitive",
                }
            ],
        }
        homepage = dist.metadata.get("Project-URL") or dist.metadata.get("Home-page")
        if homepage:
            component["externalReferences"] = [
                {"type": "website", "url": homepage.split(",", 1)[-1].strip()}
            ]
        components.append(component)

    product_ref = f"pkg:generic/paneloom@{version}"
    dependencies = [
        {
            "ref": _purl(installed[name].metadata["Name"], installed[name].version),
            "dependsOn": [
                _purl(installed[dependency].metadata["Name"], installed[dependency].version)
                for dependency in sorted(edges.get(name, set()) & names)
            ],
        }
        for name in sorted(names)
    ]
    dependencies.insert(
        0,
        {
            "ref": product_ref,
            "dependsOn": [
                _purl(installed[name].metadata["Name"], installed[name].version)
                for name in sorted(direct_names)
            ],
        },
    )
    commit_time = _git(root, "show", "-s", "--format=%cI", commit)
    return {
        "$schema": "https://cyclonedx.org/schema/bom-1.5.schema.json",
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, f'paneloom:{commit}:{scope}')}",
        "version": 1,
        "metadata": {
            "timestamp": datetime.fromisoformat(commit_time).isoformat(),
            "component": {
                "type": "application",
                "bom-ref": product_ref,
                "name": "Paneloom",
                "version": version,
            },
            "properties": [
                {"name": "paneloom:source-commit", "value": commit},
                {
                    "name": "paneloom:frozen-business-commit",
                    "value": source_identity["frozen_business_commit"],
                },
                {"name": "paneloom:python-scope", "value": scope},
            ],
        },
        "components": components,
        "dependencies": dependencies,
    }


def _npm_packages(lock: dict) -> list[dict]:
    packages = []
    for package_path, values in lock.get("packages", {}).items():
        if not package_path:
            continue
        name = values.get("name") or package_path.rsplit("node_modules/", 1)[-1]
        license_name = values.get("license") or "UNKNOWN"
        packages.append(
            {
                "name": name,
                "version": values.get("version", ""),
                "license": license_name,
                "scope": "build" if values.get("dev") else "runtime",
                "path": package_path,
            }
        )
    return sorted(packages, key=lambda item: (item["scope"], item["name"], item["version"]))


def _validate_frontend_sbom(path: Path, npm_packages: list[dict]) -> None:
    bom = json.loads(path.read_text(encoding="utf-8-sig"))
    if bom.get("bomFormat") != "CycloneDX":
        raise RuntimeError("Frontend SBOM is not a CycloneDX document.")
    expected = Counter((item["name"], item["version"]) for item in npm_packages)
    actual = Counter(
        (component.get("name", ""), component.get("version", ""))
        for component in bom.get("components", [])
    )
    if actual != expected:
        raise RuntimeError("Frontend SBOM components do not match package-lock.json.")
    missing_licenses = [
        component.get("name", "")
        for component in bom.get("components", [])
        if not component.get("licenses")
    ]
    if missing_licenses:
        raise RuntimeError(f"Frontend SBOM licenses are missing: {missing_licenses}")


def _markdown_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    output = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    output.extend("| " + " | ".join(row) + " |" for row in rows)
    return output


def _license_text(dist: metadata.Distribution) -> tuple[str, str]:
    files = _license_files(dist)
    if files:
        raw_text = "\n\n".join(
            path.read_text(encoding="utf-8", errors="replace").strip() for path in files
        )
        text = "\n".join(line.rstrip() for line in raw_text.splitlines())
        return ", ".join(path.name for path in files), text
    expression = _license_expression(dist)
    if expression == "MIT":
        holder = dist.metadata.get("Author-email") or dist.metadata.get("Author") or "See package metadata"
        return "package metadata + standard MIT text", f"Copyright metadata: {holder}\n\n{MIT_TEXT}"
    raise RuntimeError(f"No distributable license text found for {dist.metadata['Name']}")


def _write_license_inventory(
    output: Path,
    commit: str,
    runtime_names: set[str],
    build_names: set[str],
    installed: dict[str, metadata.Distribution],
    npm_packages: list[dict],
    node_modules: Path,
) -> None:
    lines = [
        "# Paneloom third-party license inventory",
        "",
        "This file is generated from the exact Python build environment and frontend lock file.",
        f"Source commit: `{commit}`",
        "",
        "It is a distribution inventory, not legal advice. Package authors retain their rights.",
        "",
        "## Python runtime",
        "",
    ]
    lines.extend(
        _markdown_table(
            ["Package", "Version", "License", "Relationship"],
            [
                [
                    installed[name].metadata["Name"],
                    installed[name].version,
                    _license_expression(installed[name]),
                    "runtime",
                ]
                for name in sorted(runtime_names)
            ],
        )
    )
    lines.extend(["", "## Python build-only", ""])
    lines.extend(
        _markdown_table(
            ["Package", "Version", "License", "Relationship"],
            [
                [
                    installed[name].metadata["Name"],
                    installed[name].version,
                    _license_expression(installed[name]),
                    "build/test",
                ]
                for name in sorted(build_names - runtime_names)
            ],
        )
    )
    lines.extend(["", "## Frontend dependencies", ""])
    lines.extend(
        _markdown_table(
            ["Package", "Version", "License", "Relationship"],
            [
                [item["name"], item["version"], item["license"], item["scope"]]
                for item in npm_packages
            ],
        )
    )
    lines.extend(["", "## License texts shipped with the binary", ""])
    redistributed_python = sorted(runtime_names | {canonicalize_name("pyinstaller")})
    for name in redistributed_python:
        dist = installed[name]
        source, license_text = _license_text(dist)
        lines.extend(
            [
                f"### {dist.metadata['Name']} {dist.version}",
                "",
                f"License: `{_license_expression(dist)}`. Source: `{source}`.",
                "",
                "```text",
                license_text,
                "```",
                "",
            ]
        )

    for item in (item for item in npm_packages if item["scope"] == "runtime"):
        package_dir = node_modules.parent / item["path"]
        candidates = sorted(
            path
            for path in package_dir.iterdir()
            if path.is_file()
            and any(token in path.name.lower() for token in ("license", "copying", "notice"))
        )
        if not candidates:
            raise RuntimeError(f"No runtime npm license file found: {item['name']}")
        license_text = "\n\n".join(
            path.read_text(encoding="utf-8", errors="replace").strip() for path in candidates
        )
        lines.extend(
            [
                f"### {item['name']} {item['version']}",
                "",
                f"License: `{item['license']}`. Source: `{', '.join(path.name for path in candidates)}`.",
                "",
                "```text",
                license_text,
                "```",
                "",
            ]
        )
    output.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--node-modules", type=Path, required=True)
    arguments = parser.parse_args()
    root = arguments.root.resolve()
    node_modules = arguments.node_modules.resolve()
    if not node_modules.is_dir():
        raise RuntimeError(f"node_modules directory does not exist: {node_modules}")

    installed = _installed_distributions()
    runtime_direct = _requirement_roots(root / "desktop" / "requirements.txt")
    build_direct = _requirement_roots(root / "requirements-build.txt")
    runtime_names, runtime_edges = _dependency_closure(runtime_direct, installed)
    build_names, build_edges = _dependency_closure(build_direct, installed)
    source_identity = json.loads((root / "release-source.json").read_text(encoding="utf-8"))
    commit = source_identity["packaging_source_commit"]
    _git(root, "merge-base", "--is-ancestor", commit, "HEAD")
    version = (root / "VERSION").read_text(encoding="utf-8").strip()
    if source_identity["version"] != version:
        raise RuntimeError("release-source.json does not match VERSION.")

    sbom_dir = root / "sbom"
    sbom_dir.mkdir(exist_ok=True)
    for filename, scope, names, direct, edges in (
        ("python-runtime.cdx.json", "runtime", runtime_names, runtime_direct, runtime_edges),
        ("python-build.cdx.json", "build", build_names, build_direct, build_edges),
    ):
        bom = _python_bom(
            root,
            version,
            commit,
            scope,
            names,
            direct,
            edges,
            installed,
            source_identity,
        )
        (sbom_dir / filename).write_text(
            json.dumps(bom, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    npm_lock = json.loads((root / "frontend" / "package-lock.json").read_text(encoding="utf-8"))
    npm_packages = _npm_packages(npm_lock)
    unknown_npm = [item for item in npm_packages if item["license"] == "UNKNOWN"]
    if unknown_npm:
        raise RuntimeError(f"Unknown npm licenses: {unknown_npm}")
    _validate_frontend_sbom(sbom_dir / "frontend.cdx.json", npm_packages)
    _write_license_inventory(
        root / "THIRD_PARTY_LICENSES.md",
        commit,
        runtime_names,
        build_names,
        installed,
        npm_packages,
        node_modules,
    )
    print(
        json.dumps(
            {
                "commit": commit,
                "python_runtime_components": len(runtime_names),
                "python_build_components": len(build_names),
                "frontend_components": len(npm_packages),
                "frontend_runtime_components": sum(
                    item["scope"] == "runtime" for item in npm_packages
                ),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
