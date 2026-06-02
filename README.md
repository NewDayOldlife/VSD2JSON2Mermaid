# VSDX to Mermaid Converter

A Python script to convert Microsoft Visio `.vsdx` files into Mermaid.js diagrams and JSON structured representations.

## Features
- **Geometry Mapping:** Automatically maps Visio shape types (Decisions, Data, Terminators) to corresponding Mermaid geometries (`{}`, `[()]`, `()`).
- **Subgraphs & Containers:** Preserves nested groupings, swimlanes, and container logic by rendering nested subgraphs in Mermaid.
- **Connector Labels:** Retains custom text written on connector arrows (e.g. `-->|Yes|`).
- **Metadata Extraction:** Extracts hidden Data Properties from Visio shapes and exports them directly into the JSON representation.

## Installation
Ensure you have Python installed, then run:

```bash
pip install -r requirements.txt
```

## Usage
Run the script passing the path to your `.vsdx` file as an argument:

```bash
python convert_vsdx.py path/to/your/file.vsdx
```

**Options:**
- `--out-json <path>`: Specifies output path for the JSON file.
- `--out-mermaid <path>`: Specifies output path for the Mermaid file.
- `--direction <TD|LR|BT|RL>`: Sets Mermaid flowchart direction (default: `TD`).
