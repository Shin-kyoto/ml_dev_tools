# Rename Dataset Tool

A tool for batch renaming annotation datasets using Web.Auto.

## Features

1. **Search**: Search for datasets using specified keywords
2. **Retrieve**: Get detailed information (including names) for each dataset
3. **Update**: Transform names based on regex rules and update datasets

## Usage

```bash
python rename_dataset.py --config example/config.yaml --dry-run
```

## Configuration File

Configuration is written in YAML format.

### Example Configuration (config/example.yaml)

```yaml
project_id: project_id

name_keywords:
  - DB_J6Gen2_v3.0_project_id
  - DB_J6Gen2_v3.0_ProjectID

rules_regexp:
  - from: '^DB_J6Gen2_v3\.0_project_id(.*)$'
    to: 'DB_J6Gen2_v3.0_DevOps_project_id\1'
  - from: '^DB_J6Gen2_v3\.0_ProjectID(.*)$'
    to: 'DB_J6Gen2_v3.0_DevOps_ProjectID\1'
```

### Configuration Fields

- **project_id**: Project ID used by Web.Auto
- **name_keywords**: List of keywords used for searching
- **rules_regexp**: List of name transformation rules
  - **from**: Regular expression pattern to match
  - **to**: Replacement string (backreferences supported)

### Regular Expression Pattern Explanation

#### Pattern: `^DB_J6Gen2_v3\.0_ProjectID(.*)$`

- `^`: Start of string
- `DB_J6Gen2_v3\.0_ProjectID`: Literal string (`.` escaped as `\.`)
- `(.*)`: Capture group - captures any characters
- `$`: End of string

#### Replacement: `DB_J6Gen2_v3.0_DevOps_ProjectID\1`

- `DB_J6Gen2_v3.0_DevOps_ProjectID`: New prefix
- `\1`: Insert content of first capture group

### Transformation Example

**Before:**
```
DB_J6Gen2_v3.0_ProjectID_f4dcbb5d-7e67-470b-8d65-c2c9dbcd813b_2025-01-01_01-00-00_01-01-00
```

**After:**
```
DB_J6Gen2_v3.0_DevOps_ProjectID_f4dcbb5d-7e67-470b-8d65-c2c9dbcd813b_2025-01-01_01-00-00_01-01-00
```

In this example, only the `DB_J6Gen2_v3.0_ProjectID` part is replaced with `DB_J6Gen2_v3.0_DevOps_ProjectID`, while the remaining parts (timestamps, UUIDs, etc.) are preserved.

## Important Notes

- Always run in dry-run mode first to verify the changes
- Design regex patterns carefully to avoid unintended modifications
- Ensure Web.Auto CLI tool is properly installed and authenticated
- Backup important data before running the actual updates
