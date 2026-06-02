import os
import sys
import json
import argparse
try:
    import vsdx
except ImportError:
    print("Error: 'vsdx' package is not installed. Please run 'pip install vsdx'")
    sys.exit(1)

def get_shape_type(shape):
    # Try to guess shape type from master shape name
    if hasattr(shape, 'master_shape') and shape.master_shape:
        name = getattr(shape.master_shape, 'name', '').lower()
        if 'decision' in name: return 'decision'
        if 'start' in name or 'end' in name or 'terminator' in name: return 'terminator'
        if 'database' in name or 'data' in name: return 'database'
        if 'process' in name: return 'process'
        if 'document' in name: return 'document'
    # Fallback to shape name if master isn't helpful
    name = getattr(shape, 'name', '').lower()
    if 'decision' in name: return 'decision'
    
    return 'default'

def extract_vsdx_data(file_path):
    data = {
        "file": os.path.basename(file_path),
        "pages": []
    }
    
    with vsdx.VisioFile(file_path) as vis:
        for page in vis.pages:
            page_data = {
                "name": page.name,
                "shapes": [],
                "connections": []
            }
            
            def extract_shapes(shapes_list):
                shapes_extracted = []
                for shape in shapes_list:
                    shape_id = getattr(shape, 'ID', None) or getattr(shape, 'id', None)
                    if shape_id is None:
                        continue
                        
                    shape_info = {
                        "id": shape_id,
                        "text": getattr(shape, 'text', '').replace('\n', ' ').strip(),
                        "type": get_shape_type(shape),
                        "metadata": {}
                    }
                    
                    # Extract Data Properties
                    try:
                        data_props = getattr(shape, 'data_properties', None)
                        if data_props:
                            for k, v in data_props.items():
                                shape_info["metadata"][k] = getattr(v, 'value', str(v))
                    except Exception:
                        pass
                    
                    # Extract Child Shapes (Subgraphs/Containers)
                    child_shapes_list = getattr(shape, 'child_shapes', getattr(shape, 'sub_shapes', None))
                    if child_shapes_list:
                        if callable(child_shapes_list):
                            child_shapes_list = child_shapes_list()
                            
                        if child_shapes_list:
                            children = extract_shapes(child_shapes_list)
                            if children:
                                shape_info["children"] = children
                                
                    shapes_extracted.append(shape_info)
                return shapes_extracted

            # Top level shapes
            if hasattr(page, 'child_shapes'):
                top_shapes = page.child_shapes
            else:
                top_shapes = page.shapes
            page_data["shapes"] = extract_shapes(top_shapes)

            # Extract connections and their labels
            flat_shapes_map = {}
            def build_flat_map(s_list):
                for s in s_list:
                    flat_shapes_map[str(s["id"])] = s
                    if "children" in s:
                        build_flat_map(s["children"])
            build_flat_map(page_data["shapes"])

            if hasattr(page, 'connects'):
                for connect in page.connects:
                    from_id = getattr(connect, 'from_shape_id', getattr(connect, 'from_id', None))
                    to_id = getattr(connect, 'to_shape_id', getattr(connect, 'to_id', None))
                    conn_shape_id = getattr(connect, 'connector_id', getattr(connect, 'connector_shape_id', None))
                    
                    if from_id is not None and to_id is not None:
                        conn_info = {
                            "from_shape_id": from_id,
                            "to_shape_id": to_id,
                            "connector_id": conn_shape_id,
                            "label": ""
                        }
                        
                        # Find connector shape text if it exists
                        if conn_shape_id:
                            conn_shape = flat_shapes_map.get(str(conn_shape_id))
                            if conn_shape and conn_shape.get("text"):
                                conn_info["label"] = conn_shape["text"]
                        
                        page_data["connections"].append(conn_info)
            
            data["pages"].append(page_data)
            
    return data

def sanitize_mermaid_id(shape_id):
    return f"node_{shape_id}"

def sanitize_mermaid_text(text):
    if not text:
        return " "
    return text.replace('"', '&quot;')

def format_mermaid_node(shape):
    m_id = sanitize_mermaid_id(shape["id"])
    text = sanitize_mermaid_text(shape["text"])
    shape_type = shape.get("type", "default")
    
    if shape_type == "decision":
        return f'{m_id}{{"{text}"}}'
    elif shape_type == "terminator":
        return f'{m_id}("{text}")'
    elif shape_type == "database":
        return f'{m_id}[("{text}")]'
    else:
        return f'{m_id}["{text}"]'

def generate_mermaid(data, direction="TD"):
    mermaid_lines = []
    
    for page in data.get("pages", []):
        mermaid_lines.append(f"%% Page: {page['name']}")
        mermaid_lines.append(f"graph {direction}")
        
        connected_ids = set()
        for conn in page.get("connections", []):
            connected_ids.add(str(conn["from_shape_id"]))
            connected_ids.add(str(conn["to_shape_id"]))
            if conn["connector_id"]:
                connected_ids.add(str(conn["connector_id"]) + "_connector")
                
        def render_shapes(shapes_list, indent="    "):
            lines = []
            for shape in shapes_list:
                s_id = str(shape["id"])
                
                # Skip rendering this node if it's a connector line
                if s_id + "_connector" in connected_ids:
                    continue

                has_children = "children" in shape and len(shape["children"]) > 0
                
                if has_children:
                    sg_id = sanitize_mermaid_id(shape["id"])
                    text = sanitize_mermaid_text(shape["text"])
                    lines.append(f'{indent}subgraph {sg_id} ["{text}"]')
                    lines.extend(render_shapes(shape["children"], indent + "    "))
                    lines.append(f'{indent}end')
                else:
                    if s_id in connected_ids or shape["text"]:
                        lines.append(f'{indent}{format_mermaid_node(shape)}')
            return lines
            
        mermaid_lines.extend(render_shapes(page.get("shapes", [])))
        
        flat_shapes_map = {}
        def build_flat_map(s_list):
            for s in s_list:
                flat_shapes_map[str(s["id"])] = s
                if "children" in s:
                    build_flat_map(s["children"])
        build_flat_map(page.get("shapes", []))
        
        for conn in page.get("connections", []):
            from_id = str(conn["from_shape_id"])
            to_id = str(conn["to_shape_id"])
            label = sanitize_mermaid_text(conn.get("label", ""))
            
            from_m_id = sanitize_mermaid_id(from_id)
            to_m_id = sanitize_mermaid_id(to_id)
            
            if label and label != " ":
                mermaid_lines.append(f'    {from_m_id} -->|"{label}"| {to_m_id}')
            else:
                mermaid_lines.append(f'    {from_m_id} --> {to_m_id}')
                
        mermaid_lines.append("")
        
    return "\n".join(mermaid_lines)

def main():
    parser = argparse.ArgumentParser(description="Convert VSDX to JSON and Mermaid format.")
    parser.add_argument("input_file", help="Path to the input .vsdx file")
    parser.add_argument("--out-json", help="Path to output JSON file. Defaults to input filename with .json", default=None)
    parser.add_argument("--out-mermaid", help="Path to output Mermaid file. Defaults to input filename with .mermaid", default=None)
    parser.add_argument("--direction", help="Mermaid graph direction (default: TD)", default="TD", choices=["TD", "LR", "BT", "RL"])
    
    args = parser.parse_args()
    
    input_path = args.input_file
    if not os.path.exists(input_path):
        print(f"Error: File '{input_path}' not found.")
        sys.exit(1)
        
    base_name = os.path.splitext(input_path)[0]
    out_json = args.out_json or f"{base_name}.json"
    out_mermaid = args.out_mermaid or f"{base_name}.mermaid"
    
    print(f"Processing '{input_path}'...")
    try:
        data = extract_vsdx_data(input_path)
    except Exception as e:
        print(f"Failed to parse VSDX file: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
        
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    print(f"Saved JSON to '{out_json}'")
    
    mermaid_content = generate_mermaid(data, direction=args.direction)
    with open(out_mermaid, "w", encoding="utf-8") as f:
        f.write(mermaid_content)
    print(f"Saved Mermaid diagram to '{out_mermaid}'")
    
    print("Conversion completed successfully!")

if __name__ == "__main__":
    main()
