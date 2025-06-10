import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import pandas as pd
import re
import os
import json
import argparse
from collections import defaultdict


def ascii_to_hex(ascii_str):
    return [f"{ord(char):02X}" for char in ascii_str]

def hex_to_ascii(hex_values):
    try:
        bytes_obj = bytes(int(h, 16) for h in hex_values)
        ascii_str = bytes_obj.decode('ascii')
        return ascii_str if all(32 <= ord(c) < 127 for c in ascii_str) else ""
    except:
        return ""


def extract_key_value_pairs(expected_value):
    results = []
    expected_value = str(expected_value).strip()

    # 1. Extract key=value pairs (dec or hex)
    kv_matches = re.findall(r'([\w\s\-\/]+?)\s*=\s*(0x[0-9A-Fa-f]+|\d+)(?:\s*\((dec)\))?', expected_value)
    for raw_key, val, dec_flag in kv_matches:
        key_clean = raw_key.strip().replace(" ", "_").replace("-", "_").replace("/", "_")
        suffix = "_dec" if dec_flag else "_hex"
        if val.startswith("0x"):
            byte = val[2:].upper()
            value = [byte[i:i+2] for i in range(0, len(byte), 2)]
        elif dec_flag:
            value = [val]
        else:
            value = [f"{int(val):02X}"]
        results.append((key_clean + suffix, value))

    # 2. Quoted ASCII strings
    quoted_strings = re.findall(r'"(.*?)"', expected_value)
    for i, text in enumerate(quoted_strings):
        key = f"PlannedRelease{i+1}_hex" if len(quoted_strings) > 1 else "PlannedRelease_hex"
        value = ascii_to_hex(text)
        results.append((key, value))

    # 3. Loose hex patterns
    loose_hex = re.findall(r'0x[0-9A-Fa-f]{2}', expected_value)
    if loose_hex:
        values = [hx[2:].upper() for hx in loose_hex]
        results.append(("Value", values))

    # 4. Raw hex or dec bytes
    if not results:
        raw_parts = re.findall(r'[0-9A-Fa-f]{2}', expected_value)
        if raw_parts:
            results.append(("Value", [p.upper() for p in raw_parts]))

    return results



def infer_category(did):
    if did.startswith("F1"):
        return "Core Diagnostic IDs"
    elif did.startswith("F18"):
        return "Application/Boot Data"
    elif did.startswith("F13"):
        return "ECU / EBOM Info"
    elif did.startswith("F11"):
        return "Identification"
    elif did.startswith("FD") or did.startswith("$FD"):
        return "Magna Internal DIDs"
    else:
        return "Miscellaneous"

def load_mapping(map_path):
    if os.path.exists(map_path):
        try:
            with open(map_path) as f:
                return json.load(f)
        except Exception:
            print("Mapping file is corrupted. Falling back to original DIDs.")
    return {}

def save_mapping(preview_data, map_path):
    existing = load_mapping(map_path)

    for row in preview_data:
        original = row.get("Original DID", "").replace("$", "")
        current_did = row.get("DID", "")
        variable_name = row.get("Variable Name", "")
        if original:
            existing[original] = {
                "DID": current_did,
                "VariableName": variable_name,
                "Field": row.get("Field", ""),
                "HexValue": row.get("Hex Value", "")
            }

    with open(map_path, "w") as f:  
        json.dump(existing, f, indent=2)

def process_excel_to_preview(xlsx_path, release_tab, mapping=None):
    df = pd.read_excel(xlsx_path, sheet_name=release_tab)
    filtered_df = df[["DID", "Expected Value"]].dropna()

    preview_data = []
    name_counter = defaultdict(int)

    for _, row in filtered_df.iterrows():
        did_raw = str(row["DID"]).strip()
        did = did_raw.replace("$", "")
        if mapping and did in mapping:
            mapped_did = mapping[did].get("DID", did)
        else:
            mapped_did = did

        expected_val = str(row["Expected Value"]).strip()
        category = infer_category(mapped_did)

        parsed_fields = extract_key_value_pairs(expected_val)

        for suffix, hex_values in parsed_fields:
            hex_string = " ".join(hex_values)
            ascii_preview = hex_to_ascii(hex_values)
            base_var = f"{mapped_did}_{suffix}" if suffix != "Value" else mapped_did
            name_counter[base_var] += 1
            unique_var_name = base_var if name_counter[base_var] == 1 else f"{base_var}_{name_counter[base_var]}"
            if mapping and did in mapping:
                mapped = mapping[did]
                if "DID" in mapped:
                    mapped_did = mapped["DID"]
                if "VariableName" in mapped:
                    unique_var_name = mapped["VariableName"]
                if "Field" in mapped:
                    suffix = mapped["Field"]
                if "HexValue" in mapped:
                    hex_string = mapped["HexValue"]

def process_excel_to_preview(xlsx_path, release_tab, mapping=None):
    df = pd.read_excel(xlsx_path, sheet_name=release_tab)
    filtered_df = df[["DID", "Expected Value"]].dropna()

    preview_data = []
    name_counter = defaultdict(int)

    for _, row in filtered_df.iterrows():
        did_raw = str(row["DID"]).strip()
        did = did_raw.replace("$", "")
        expected_val = str(row["Expected Value"]).strip()

        if mapping and did in mapping:
            mapped_did = mapping[did].get("DID", did)
        else:
            mapped_did = did

        category = infer_category(mapped_did)
        parsed_fields = extract_key_value_pairs(expected_val)

        component_match = re.search(r'([\w\s\-]+?)\s*=', expected_val)
        component = component_match.group(1).strip().replace(" ", "").replace("-", "_") if component_match else "Field"

        for suffix, hex_values in parsed_fields:
            hex_string = " ".join(hex_values)
            ascii_preview = hex_to_ascii(hex_values)
            field_label = suffix
            base_var = f"{mapped_did}_{component}_{suffix}" if suffix != "Value" else f"{mapped_did}_{component}"
            name_counter[base_var] += 1
            unique_var_name = base_var if name_counter[base_var] == 1 else f"{base_var}_{name_counter[base_var]}"

            if mapping and did in mapping:
                mapped = mapping[did]
                if "DID" in mapped:
                    mapped_did = mapped["DID"]
                if "VariableName" in mapped:
                    unique_var_name = mapped["VariableName"]
                if "Field" in mapped:
                    field_label = mapped["Field"]
                if "HexValue" in mapped:
                    hex_string = mapped["HexValue"]
                    hex_values = hex_string.split()
                    ascii_preview = hex_to_ascii(hex_values)

            preview_data.append({
                "Original DID": did,
                "DID": mapped_did,
                "Field": field_label,
                "Variable Name": unique_var_name,
                "Hex Value": hex_string,
                "ASCII Preview": ascii_preview,
                "Category": category
            })

    return preview_data

    xlsx_path = tk.StringVar()
    release_tab = tk.StringVar()
    release_tabs = []
    preview_data = []
    mapping_file = tk.StringVar()

    def import_vparam_file():
        file_path = filedialog.askopenfilename(filetypes=[("vParam Files", "*.vparam")])
        if not file_path: return
        with open(file_path, "r") as f:
            lines = f.readlines()

        start = False
        for line in lines:
            if line.strip().startswith("Name"):  # header found
                start = True
                continue
            if start and line.strip():
                parts = line.strip().split("\t")
                if len(parts) >= 4:
                    preview_data.append({
                        "Original DID": parts[0].split("_")[0].replace("$", ""),
                        "DID": parts[0].split("_")[0],
                        "Field": "_".join(parts[0].split("_")[1:]) or "Value",
                        "Variable Name": parts[0],
                        "Hex Value": parts[3],
                        "ASCII Preview": hex_to_ascii(parts[3].split()),
                        "Category": "Imported vParam"
                    })
        populate_table()

    def browse_excel():
        path = filedialog.askopenfilename(filetypes=[("Excel Files", "*.xlsx")])
        if path:
            xlsx_path.set(path)
            update_tabs(path)

    def delete_selected_row(event=None):
        selected = table.selection()
        for item in selected:
            table.delete(item)
            del preview_data[int(item)]
            
    def delete_selected_row(event=None):
        selected_items = table.selection()
        for item in selected_items:
            table.delete(item)
            preview_data.pop(int(item))

    def clear_table():
        nonlocal preview_data  # if inside a nested function like run_gui()
        preview_data.clear()
        table.delete(*table.get_children())

    def update_tabs(path):
        try:
            xls = pd.ExcelFile(path)
            tab_menu["menu"].delete(0, "end")
            release_tabs.clear()
            release_tabs.extend(xls.sheet_names)
            release_tab.set(release_tabs[0])
            for t in release_tabs:
                tab_menu["menu"].add_command(label=t, command=tk._setit(release_tab, t))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def generate_preview():
        nonlocal preview_data
        try:
            map_file = mapping_file.get()
            if not map_file and xlsx_path.get():
                base = os.path.splitext(xlsx_path.get())[0]
                map_file = base + "_mappings.json"
                mapping_file.set(map_file)

            mapping = load_mapping(map_file)
            new_rows = process_excel_to_preview(xlsx_path.get(), release_tab.get(), mapping)

            existing_by_did = {row["DID"]: row for row in preview_data}
            for new_row in new_rows:
                did = new_row["DID"]
                if did in existing_by_did:
                    old_row = existing_by_did[did]
                    new_row["Hex Value"] = old_row.get("Hex Value", new_row["Hex Value"])
                    new_row["ASCII Preview"] = hex_to_ascii(new_row["Hex Value"].split())
                existing_by_did[did] = new_row

            preview_data = list(existing_by_did.values())
            populate_table()
        except Exception as e:
            messagebox.showerror("Error", str(e))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def populate_table():
        for row in table.get_children():
            table.delete(row)
        for i, item in enumerate(preview_data):
            table.insert("", "end", iid=i, values=(item["DID"], item["Field"], item["Variable Name"], item["Hex Value"], item["ASCII Preview"]))

    def on_edit(event):
     item_id = table.identify_row(event.y)
     column = table.identify_column(event.x)
     col_index = int(column.replace('#', '')) - 1
     if col_index not in [0, 1, 2, 3]:  # DID, Field, Var Name, Hex Value
         return

     x, y, width, height = table.bbox(item_id, column)
     current_values = table.item(item_id, 'values')
     entry = tk.Entry(root)
     entry.place(x=x + table.winfo_rootx() - root.winfo_rootx(),
                 y=y + table.winfo_rooty() - root.winfo_rooty(),
                 width=width, height=height)
     entry.insert(0, current_values[col_index])
     entry.focus()

     def save_edit(event):
         new_val = entry.get().strip()
         if col_index == 0:
             preview_data[int(item_id)]["DID"] = new_val
         elif col_index == 1:
             preview_data[int(item_id)]["Field"] = new_val
         elif col_index == 2:
             preview_data[int(item_id)]["Variable Name"] = new_val
         elif col_index == 3:
             preview_data[int(item_id)]["Hex Value"] = new_val
         entry.destroy()
         populate_table()

     entry.bind("<Return>", save_edit)
     entry.bind("<FocusOut>", lambda e: entry.destroy())


    
    def insert_new_row():
        new_entry = {
            "Original DID": "NEW",
            "DID": "NEW",
            "Field": "Field",
            "Variable Name": "NEW_Field",
            "Hex Value": "",
            "ASCII Preview": "",
            "Category": "User Inserted"
        }
        preview_data.append(new_entry)
        populate_table()

    def regenerate_output():
        try:
            # Sync UI edits to preview_data
            for i, item_id in enumerate(table.get_children()):
                values = table.item(item_id, "values")
                preview_data[i]["DID"] = values[0]
                preview_data[i]["Field"] = values[1]
                preview_data[i]["Variable Name"] = values[2]
                preview_data[i]["Hex Value"] = values[3]
                preview_data[i]["ASCII Preview"] = values[4]

            if not mapping_file.get() and xlsx_path.get():
                base = os.path.splitext(xlsx_path.get())[0]
                mapping_file.set(base + "_mappings.json")

            out_vparam = os.path.splitext(xlsx_path.get())[0] + "_Auto.vparam"
            out_excel = os.path.splitext(xlsx_path.get())[0] + "_Auto.xlsx"

            export_outputs(preview_data, out_vparam, out_excel)
            save_mapping(preview_data, mapping_file.get())
            messagebox.showinfo("Done", f"Files saved:\n{out_vparam}\n{out_excel}\n{mapping_file.get()}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    tk.Label(root, text="Excel File:").grid(row=0, column=0, sticky="w")
    tk.Entry(root, textvariable=xlsx_path, width=60).grid(row=0, column=1)
    tk.Button(root, text="Browse", command=browse_excel).grid(row=0, column=2)
    tk.Button(root, text="Import vParam File", command=import_vparam_file).grid(row=1, column=2)
    
    tk.Label(root, text="Release Tab:").grid(row=1, column=0, sticky="w")
    tab_menu = tk.OptionMenu(root, release_tab, "")
    tab_menu.grid(row=1, column=1, sticky="ew")

    tk.Label(root, text="Mapping File (Optional):").grid(row=2, column=0, sticky="w")
    tk.Entry(root, textvariable=mapping_file, width=60).grid(row=2, column=1)

   

    table = ttk.Treeview(root, columns=("DID", "Field", "Variable Name", "Hex Value", "ASCII Preview"), show="headings", height=14)

    for col in table["columns"]:
        table.heading(col, text=col)
        table.column(col, width=120)
    table.grid(row=4, column=0, columnspan=3, padx=10, pady=10)
    table.bind("<Double-1>", on_edit)
    table.bind("<Delete>", delete_selected_row)

    tk.Button(root, text="Delete Selected Row", command=delete_selected_row, bg="#f44336", fg="white").grid(row=5, column=0, pady=5)
    tk.Button(root, text="Generate Preview", command=generate_preview, bg="#4CAF50", fg="white").grid(row=3, column=0, columnspan=3, pady=5)
    tk.Button(root, text="Insert New Row", command=insert_new_row, bg="#FF9800", fg="white").grid(row=5, column=2, pady=5)
    tk.Button(root, text="Re-Generate Outputs", command=regenerate_output, bg="#2196F3", fg="white").grid(row=5, column=1, columnspan=3, pady=10)
    tk.Button(root, text="Clear Table", command=clear_table, bg="#9E9E9E", fg="white").grid(row=3, column=2, pady=3)

    root.mainloop()

def export_outputs(preview_data, output_vparam_path, output_excel_path):
    # Export Vector-format .vparam file
    with open(output_vparam_path, "w") as f:
        f.write("Vector Parameter\t1.0\n\n")
        f.write("ScalarSingleRecord\n\n")
        f.write("Name\tType\tInfo\tValue\n")
        for row in preview_data:
            f.write(f"{row['Variable Name']}\tString\t{row['Field']}\t{row['Hex Value']}\n")

    # Export Excel file
    df = pd.DataFrame(preview_data)
    df.to_excel(output_excel_path, index=False)


def run_cli(args):
    try:
        args.ignore_mapping = True
        if not args.mapping_file:
            base = os.path.splitext(args.xlsx_path)[0]
            args.mapping_file = base + "_mappings.json"
        mapping = {} if args.ignore_mapping else load_mapping(args.mapping_file)
        preview_data = process_excel_to_preview(args.xlsx_path, args.release_tab, mapping)
        print(f"[DEBUG] Parsed {len(preview_data)} entries from Excel ({args.release_tab})")
        export_outputs(preview_data, args.output_vparam, args.output_excel)
        save_mapping(preview_data, args.mapping_file)
        print(f" vParam file saved to: {args.output_vparam}")
        print(f" Excel validation saved to: {args.output_excel}")
        print(f" Mapping saved to: {args.mapping_file}")
    except Exception as e:
        print(e)

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    default_vparam_path = os.path.join(base_dir, "SanityTest.src", "Diag_Params.vparam")
    print("Default vparam path: "+default_vparam_path)
    
    parser = argparse.ArgumentParser(description="vParam Tool (CLI or GUI)")
    parser.add_argument("--cli", action="store_true", help="Run in CLI mode")
    parser.add_argument("--xlsx_path", default="C:\\_mks\\KP03_ProductEngineering\\40_Software\\40_Release\\L2H7010_SW_part_number_matrix.xlsx", help="Excel file path")
    parser.add_argument("--release_tab", required=False, default=None, help="Excel sheet name (default: latest)")
    parser.add_argument("--output_vparam", default=default_vparam_path, help="Output .vparam path")
    parser.add_argument("--output_excel", default="Diag_Params.xlsx", help="Output Excel path")
    parser.add_argument("--ignore_mapping", action="store_true", default=True, help="Ignore mapping file and use only Excel")
    parser.add_argument("--mapping_file", default=None, help="Mapping file path")

    args = parser.parse_args()
    # Default to latest sheet if none provided
    if args.release_tab is None:
        xls = pd.ExcelFile(args.xlsx_path)
        args.release_tab = xls.sheet_names[-1]
        print(f"[INFO] Using latest Excel tab: {args.release_tab}")
    if args.cli or args.xlsx_path and args.release_tab:
        run_cli(args)
    else:
        run_gui()



