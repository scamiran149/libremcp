# md2xhp — Markdown to LibreOffice XHP Help Converter

Converts a subset of Markdown to LibreOffice `.xhp` help files
for integration into extensions.

## Supported Markdown Subset

```
# Heading 1
## Heading 2
### Heading 3

Regular paragraph text.

**bold text**
*italic text*
`inline code`

- Unordered list item
- Another item

1. Ordered list item
2. Another item

```code block```

> Note/tip block

[link text](url)

![image alt](path)

---  (horizontal rule / section break)
```

## Usage

```bash
python md2xhp.py input.md -o output.xhp
python md2xhp.py help/ -o build/help/   # batch convert directory
```

## XHP Output

Each `.md` file produces one `.xhp` file suitable for inclusion
in a LibreOffice extension's help package.

## Integration

Add to `extension/META-INF/manifest.xml`:
```xml
<manifest:file-entry manifest:media-type="application/vnd.sun.star.help"
                     manifest:full-path="help/"/>
```
