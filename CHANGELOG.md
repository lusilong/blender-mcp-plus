# Changelog

All notable changes to this project are documented here.
This project follows [Semantic Versioning](https://semver.org/).

## [1.0.3] - 2026-11-02

First standalone release of Blender MCP Plus, derived from Blender Lab's
`blender_mcp` 1.0.2 (commit `dbbf836`).

### Added

- `search_assets` tool: search Poly Haven's free CC0 library of models, HDRIs and
  textures (filters: query, asset type, category, minimum real-world size).
- `import_asset` tool:
  - models: download and import glTF, optional scaling to a target size in meters;
  - HDRIs: download EXR/HDR and set it as the world environment with a strength;
  - textures: download the diffuse map and apply a new material to a target object.
- MCP Bundle (`manifest.json`) and cross-platform `scripts/build_mcpb.py`.
- One-click release script `scripts/publish.ps1` (GitHub repo/release + optional PyPI).
- GitHub Actions workflows for CI and tagged releases (PyPI Trusted Publishing).

### Fixed

- `execute_blender_code_for_cli` and the `*_for_cli` tools no longer hang for 120 s
  when the MCP server is launched with piped stdio (for example by an MCP client).
  Child process output is captured through temporary files instead of inherited pipes.

### Changed

- Python package renamed from `blmcp` to `blender_mcp_plus`; console script is now
  `blender-mcp-plus` so it can coexist with the upstream `blender-mcp` package.
