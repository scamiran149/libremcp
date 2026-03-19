#!/usr/bin/env python3
"""md2xhp — Convert Markdown to LibreOffice XHP help format.

Supports a minimal Markdown subset. No external dependencies.

Usage:
    python md2xhp.py input.md -o output.xhp
    python md2xhp.py help_dir/ -o build/help/
"""

import argparse
import os
import re
import sys
from xml.sax.saxutils import escape

# XHP namespace and boilerplate
XHP_HEADER = '''\
<?xml version="1.0" encoding="UTF-8"?>
<helpdocument version="1.0">
<meta>
  <topic id="{topic_id}" indexer="include" status="PUBLISH">
    <title id="tit" xml-lang="en-US">{title}</title>
  </topic>
</meta>
<body>
'''

XHP_FOOTER = '''\
</body>
</helpdocument>
'''


def md_to_xhp(md_text, topic_id="topic"):
    """Convert Markdown text to XHP XML string."""
    lines = md_text.split("\n")
    out = []
    title = topic_id
    in_code_block = False
    in_list = False
    list_type = None  # "ul" or "ol"

    i = 0
    while i < len(lines):
        line = lines[i]

        # Code block (fenced)
        if line.strip().startswith("```"):
            if in_code_block:
                in_code_block = False
                i += 1
                continue
            else:
                in_code_block = True
                # Collect code block content
                code_lines = []
                i += 1
                while i < len(lines) and not lines[i].strip().startswith("```"):
                    code_lines.append(lines[i])
                    i += 1
                code_text = escape("\n".join(code_lines))
                out.append(
                    '<paragraph role="code" xml-lang="en-US">'
                    '%s</paragraph>' % code_text)
                if i < len(lines):
                    i += 1  # skip closing ```
                in_code_block = False
                continue

        # Empty line — close list if open
        if not line.strip():
            if in_list:
                out.append("</list>")
                in_list = False
                list_type = None
            i += 1
            continue

        # Headings
        m = re.match(r'^(#{1,6})\s+(.*)', line)
        if m:
            level = len(m.group(1))
            text = m.group(2).strip()
            if level == 1 and title == topic_id:
                title = text
            out.append(
                '<paragraph role="heading" id="hd_%d_%d" '
                'level="%d" xml-lang="en-US">%s</paragraph>'
                % (level, i, level, _inline(text)))
            i += 1
            continue

        # Horizontal rule
        if re.match(r'^---+\s*$', line):
            out.append('<section id="sep_%d">' % i)
            out.append('</section>')
            i += 1
            continue

        # Unordered list
        m = re.match(r'^[-*+]\s+(.*)', line)
        if m:
            if not in_list or list_type != "ul":
                if in_list:
                    out.append("</list>")
                out.append('<list type="unordered">')
                in_list = True
                list_type = "ul"
            out.append(
                '<listitem><paragraph role="listitem" xml-lang="en-US">'
                '%s</paragraph></listitem>' % _inline(m.group(1)))
            i += 1
            continue

        # Ordered list
        m = re.match(r'^\d+\.\s+(.*)', line)
        if m:
            if not in_list or list_type != "ol":
                if in_list:
                    out.append("</list>")
                out.append('<list type="ordered">')
                in_list = True
                list_type = "ol"
            out.append(
                '<listitem><paragraph role="listitem" xml-lang="en-US">'
                '%s</paragraph></listitem>' % _inline(m.group(1)))
            i += 1
            continue

        # Blockquote (note/tip)
        m = re.match(r'^>\s*(.*)', line)
        if m:
            out.append(
                '<paragraph role="note" xml-lang="en-US">'
                '%s</paragraph>' % _inline(m.group(1)))
            i += 1
            continue

        # Regular paragraph
        if in_list:
            out.append("</list>")
            in_list = False
            list_type = None
        out.append(
            '<paragraph role="paragraph" xml-lang="en-US">'
            '%s</paragraph>' % _inline(line))
        i += 1

    if in_list:
        out.append("</list>")

    header = XHP_HEADER.format(topic_id=escape(topic_id),
                                title=escape(title))
    return header + "\n".join(out) + "\n" + XHP_FOOTER


def _inline(text):
    """Convert inline Markdown to XHP inline elements."""
    text = escape(text)

    # Bold **text**
    text = re.sub(r'\*\*(.+?)\*\*',
                  r'<emph>\1</emph>', text)

    # Italic *text*
    text = re.sub(r'\*(.+?)\*',
                  r'<emph>\1</emph>', text)

    # Inline code `text`
    text = re.sub(r'`(.+?)`',
                  r'<item type="literal">\1</item>', text)

    # Links [text](url)
    text = re.sub(r'\[(.+?)\]\((.+?)\)',
                  r'<link href="\2">\1</link>', text)

    # Images ![alt](path) — just show alt text
    text = re.sub(r'!\[(.+?)\]\((.+?)\)',
                  r'<image src="\2" id="img"><alt>\1</alt></image>', text)

    return text


def convert_file(input_path, output_path=None):
    """Convert a single .md file to .xhp."""
    with open(input_path, "r", encoding="utf-8") as f:
        md_text = f.read()

    basename = os.path.splitext(os.path.basename(input_path))[0]
    topic_id = basename.replace(" ", "_").replace("-", "_")
    xhp = md_to_xhp(md_text, topic_id)

    if output_path is None:
        output_path = os.path.splitext(input_path)[0] + ".xhp"

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(xhp)

    print("  %s -> %s" % (input_path, output_path))
    return output_path


def convert_dir(input_dir, output_dir):
    """Convert all .md files in a directory."""
    results = []
    for fn in sorted(os.listdir(input_dir)):
        if fn.endswith(".md"):
            inp = os.path.join(input_dir, fn)
            out = os.path.join(output_dir,
                               fn.replace(".md", ".xhp"))
            results.append(convert_file(inp, out))
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Convert Markdown to LibreOffice XHP help files")
    parser.add_argument("input", help="Input .md file or directory")
    parser.add_argument("-o", "--output", default=None,
                        help="Output .xhp file or directory")
    args = parser.parse_args()

    if os.path.isdir(args.input):
        out_dir = args.output or "build/help"
        print("Converting directory: %s -> %s" % (args.input, out_dir))
        results = convert_dir(args.input, out_dir)
        print("Converted %d files." % len(results))
    else:
        convert_file(args.input, args.output)


if __name__ == "__main__":
    main()
