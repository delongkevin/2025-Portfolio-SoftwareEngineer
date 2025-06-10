import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os, time, threading, re, webbrowser
from lxml import etree
import pdfkit
from html import escape

def parse_and_preserve_format(xml_file):
    parser = etree.XMLParser(recover=True)
    tree = etree.parse(xml_file, parser)
    return tree.getroot()

def extract_toc_links(elem, toc_links):
    raw_text = etree.tostring(elem, encoding="unicode", method="html")
    text_only = re.sub(r"<[^>]+>", "", raw_text).strip()
    if any(k in text_only.lower() for k in ['pass', 'fail', 'test']):
        anchor = re.sub(r"\W+", "_", text_only.lower())
        toc_links.append((text_only, anchor))
    for child in elem:
        extract_toc_links(child, toc_links)

def xml_to_html_with_format(elem, level=0):
    indent = "  " * level
    uid = f"node-{id(elem)}"
    has_children = len(elem) > 0
    tag_name = escape(elem.tag)
    raw_html = etree.tostring(elem, encoding="unicode", method="html")
    text_only = re.sub(r"<[^>]+>", "", raw_html).strip()
    anchor_name = ""
    if any(k in text_only.lower() for k in ['pass', 'fail', 'test']):
        anchor_name = re.sub(r"\W+", "_", text_only.lower())

    html = f'{indent}<li>'
    if has_children:
        html += f'<span class="toggle" onclick="toggleVisibility(\'{uid}\')">▶</span> '

    if anchor_name:
        html += f'<a name="{anchor_name}"></a>'

    html += f'<strong>{tag_name}</strong>'

    if elem.attrib:
        attr_str = " ".join([f'{escape(k)}="{escape(v)}"' for k, v in elem.attrib.items()])
        html += f' <em>({attr_str})</em>'

    if elem.tag.lower() == "img" and 'src' in elem.attrib:
        img_path = elem.attrib['src']
        html += f'<br><img src="{img_path}" style="max-width:600px; max-height:400px;"><br>'
    elif elem.tag.lower() == "log":
        log_text = text_only
        html += f'<pre style="background:#111; padding:10px; max-height:300px; overflow:auto;">{escape(log_text)}</pre>'
    elif text_only:
        html += f": {raw_html.strip()}"

    if has_children:
        html += f'\n<ul id="{uid}" style="display:none;">\n'
        for child in elem:
            html += xml_to_html_with_format(child, level + 1)
        html += f'{indent}</ul>\n'

    html += "</li>\n"
    return html

def generate_html_content(root):
    toc_links = []
    extract_toc_links(root, toc_links)
    html = """<!DOCTYPE html>
<html>
<head>
    <meta charset='UTF-8'>
    <title>XML Viewer</title>
    <style>
        body { background-color: #1e1e1e; color: #e0e0e0; font-family: Consolas, monospace; padding: 20px; }
        ul { list-style-type: none; padding-left: 20px; }
        li { margin: 4px 0; }
        em { color: #87CEFA; }
        strong { color: #FFD700; }
        .toggle { cursor: pointer; color: #00FF7F; font-weight: bold; }
        .highlight { background-color: yellow; color: black; font-weight: bold; }
        a.toc { color: #00CED1; text-decoration: none; display: block; margin-bottom: 5px; }
    </style>
    <script>
        function toggleVisibility(id) {
            const el = document.getElementById(id);
            el.style.display = (el.style.display === 'none') ? 'block' : 'none';
        }
        function searchNodes() {
            const keyword = document.getElementById("searchBox").value.toLowerCase();
            const lis = document.querySelectorAll("li");
            lis.forEach(li => {
                if (li.innerText.toLowerCase().includes(keyword)) {
                    li.classList.add("highlight");
                } else {
                    li.classList.remove("highlight");
                }
            });
        }
    </script>
</head>
<body>
    <h2>XML Viewer (With TOC, Search & Tree)</h2>
    <input type="text" id="searchBox" placeholder="Search PASS/FAIL/Test..." oninput="searchNodes()" 
           style="width: 40%; padding: 5px; font-size: 16px; margin-bottom: 20px;"><br>
    <h3>📌 Table of Contents</h3>
"""
    for text, anchor in toc_links:
        html += f'<a class="toc" href="#{anchor}">{escape(text)}</a>\n'

    html += "<ul>\n" + xml_to_html_with_format(root) + "</ul>\n</body>\n</html>"
    return html

def convert_xml_to_html(xml_path, html_path):
    root = parse_and_preserve_format(xml_path)
    html = generate_html_content(root)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    return html_path

def convert_to_pdf(html_path, pdf_path):
    try:
        pdfkit.from_file(html_path, pdf_path)
        return pdf_path
    except Exception as e:
        messagebox.showerror("PDF Error", f"PDF export failed: {e}")
        return None

def browse_file():
    file_path = filedialog.askopenfilename(filetypes=[("XML Files", "*.xml")])
    if file_path:
        entry_var.set(file_path)

def update_progress_bar():
    for i in range(101):
        progress_var.set(i)
        time.sleep(0.005)
    progress_bar.stop()

def run_conversion():
    xml_file = entry_var.get()
    if not xml_file or not os.path.exists(xml_file):
        messagebox.showwarning("Invalid File", "Please select a valid XML file.")
        return

    html_file = os.path.splitext(xml_file)[0] + ".html"
    pdf_file = os.path.splitext(xml_file)[0] + ".pdf"

    threading.Thread(target=update_progress_bar, daemon=True).start()

    try:
        convert_xml_to_html(xml_file, html_file)
        if export_pdf_var.get():
            convert_to_pdf(html_file, pdf_file)
        messagebox.showinfo("Success", f"HTML created:\n{html_file}")
        webbrowser.open(f"file://{os.path.abspath(html_file)}")
    except Exception as e:
        messagebox.showerror("Conversion Failed", str(e))

def drop_file(event):
    dropped_file = event.data.strip('{}')
    if dropped_file.endswith('.xml') and os.path.exists(dropped_file):
        entry_var.set(dropped_file)

root = tk.Tk()
root.title("Final XML to HTML Report Generator")
root.geometry("650x300")
root.resizable(False, False)

try:
    root.tk.call('tkdnd::drag_source', 'register', root._w, '*')
    root.tk.call('tkdnd::drop_target', 'register', root._w, '*')
    root.bind('<Drop>', drop_file)
except tk.TclError:
    pass

entry_var = tk.StringVar()
export_pdf_var = tk.BooleanVar()

tk.Label(root, text="Select or Drop XML File:").pack(pady=5)
frame = tk.Frame(root)
frame.pack()
entry = tk.Entry(frame, textvariable=entry_var, width=60)
entry.pack(side=tk.LEFT, padx=5)
tk.Button(frame, text="Browse", command=browse_file).pack(side=tk.LEFT)

tk.Checkbutton(root, text="Export as PDF", variable=export_pdf_var).pack(pady=5)

tk.Button(root, text="Convert to HTML", command=lambda: threading.Thread(target=run_conversion, daemon=True).start(),
          width=30, bg="green", fg="white").pack(pady=10)

progress_var = tk.DoubleVar()
progress_bar = ttk.Progressbar(root, variable=progress_var, maximum=100, mode='determinate', length=500)
progress_bar.pack(pady=5)

tk.Label(root, text="Search inside exported HTML to highlight nodes (real-time)", font=("Arial", 9)).pack(pady=3)

root.mainloop()
