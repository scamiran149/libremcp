# Copyright (c) David Berlioz
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Style inspection and modification tools for all document types."""

import logging

from plugin.framework.tool_base import ToolBase

log = logging.getLogger("libremcp.writer")

_SETTABLE_PROPS = {
    "ParagraphStyles": {
        "CharFontName": {
            "type": "string",
            "description": "Font name (e.g. 'Liberation Serif')",
        },
        "CharHeight": {
            "type": "number",
            "description": "Font size in points (e.g. 12)",
        },
        "CharWeight": {
            "type": "number",
            "description": "Font weight (100=thin, 150=normal, 200=bold via com.sun.star.awt.FontWeight)",
        },
        "CharPosture": {
            "type": "number",
            "description": "Italic: 0=none, 2=italic (com.sun.star.awt.FontSlant.ITALIC)",
        },
        "CharColor": {
            "type": "integer",
            "description": "Font color as RGB integer (e.g. 0xFF0000 for red)",
        },
        "ParaAdjust": {
            "type": "integer",
            "description": "Alignment: 0=left, 1=right, 2=center, 3=justify",
        },
        "ParaTopMargin": {
            "type": "number",
            "description": "Top margin in mm (converted to 1/100mm internally)",
        },
        "ParaBottomMargin": {"type": "number", "description": "Bottom margin in mm"},
        "ParaLeftMargin": {"type": "number", "description": "Left margin in mm"},
        "ParaRightMargin": {"type": "number", "description": "Right margin in mm"},
        "ParaLineSpacing": {
            "type": "number",
            "description": "Line spacing as a multiplier (1.0=single, 1.5, 2.0=double)",
        },
    },
    "CharacterStyles": {
        "CharFontName": {"type": "string", "description": "Font name"},
        "CharHeight": {"type": "number", "description": "Font size in points"},
        "CharWeight": {"type": "number", "description": "Font weight"},
        "CharPosture": {"type": "number", "description": "Italic: 0=none, 2=italic"},
        "CharColor": {"type": "integer", "description": "Font color as RGB integer"},
    },
}


_FAMILY_READ_PROPS = {
    "ParagraphStyles": [
        "ParentStyle",
        "FollowStyle",
        "CharFontName",
        "CharHeight",
        "CharWeight",
        "ParaAdjust",
        "ParaTopMargin",
        "ParaBottomMargin",
    ],
    "CharacterStyles": [
        "ParentStyle",
        "CharFontName",
        "CharHeight",
        "CharWeight",
        "CharPosture",
        "CharColor",
    ],
    "CellStyles": [
        "ParentStyle",
        "CellBackColor",
    ],
}


class ListStyles(ToolBase):
    """List available styles in a given family."""

    name = "list_styles"
    tier = "core"
    intent = "edit"
    description = (
        "List available styles in the document. "
        "Omit family to list all available style families. "
        "Works on all document types (Writer, Calc, Draw, Impress)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "family": {
                "type": "string",
                "description": (
                    "Style family to list (e.g. ParagraphStyles, "
                    "CellStyles, PageStyles). Omit to list families."
                ),
            },
        },
        "required": [],
    }
    doc_types = None  # all document types

    def execute(self, ctx, **kwargs):
        family = kwargs.get("family")
        doc = ctx.doc
        families = doc.getStyleFamilies()

        # No family specified → list available families
        if not family:
            available = list(families.getElementNames())
            return {
                "status": "ok",
                "families": available,
                "count": len(available),
            }

        if not families.hasByName(family):
            available = list(families.getElementNames())
            return {
                "status": "error",
                "message": "Unknown style family: %s" % family,
                "available_families": available,
            }

        style_family = families.getByName(family)
        styles = []
        for name in style_family.getElementNames():
            style = style_family.getByName(name)
            entry = {
                "name": name,
                "is_user_defined": style.isUserDefined(),
                "is_in_use": style.isInUse(),
            }
            try:
                entry["parent_style"] = style.getPropertyValue("ParentStyle")
            except Exception:
                pass
            styles.append(entry)

        return {
            "status": "ok",
            "family": family,
            "styles": styles,
            "count": len(styles),
        }


class GetStyleInfo(ToolBase):
    """Get detailed properties of a named style."""

    name = "get_style_info"
    tier = "core"
    intent = "edit"
    description = (
        "Get detailed properties of a specific style "
        "(font, size, margins, etc.). "
        "Works on all document types."
    )
    parameters = {
        "type": "object",
        "properties": {
            "style_name": {
                "type": "string",
                "description": "Name of the style to inspect.",
            },
            "family": {
                "type": "string",
                "description": (
                    "Style family (e.g. ParagraphStyles, CellStyles). "
                    "Default: first available family."
                ),
            },
        },
        "required": ["style_name"],
    }
    doc_types = None  # all document types

    def execute(self, ctx, **kwargs):
        style_name = kwargs.get("style_name", "")
        family = kwargs.get("family")

        if not style_name:
            return {"status": "error", "message": "style_name is required."}

        doc = ctx.doc
        families = doc.getStyleFamilies()

        # Default to first family if not specified
        if not family:
            family = families.getElementNames()[0]

        if not families.hasByName(family):
            return {
                "status": "error",
                "message": "Unknown style family: %s" % family,
                "available_families": list(families.getElementNames()),
            }

        style_family = families.getByName(family)
        if not style_family.hasByName(style_name):
            return {
                "status": "error",
                "message": "Style '%s' not found in %s." % (style_name, family),
            }

        style = style_family.getByName(style_name)
        info = {
            "name": style_name,
            "family": family,
            "is_user_defined": style.isUserDefined(),
            "is_in_use": style.isInUse(),
        }
        for prop_name in _FAMILY_READ_PROPS.get(family, []):
            try:
                info[prop_name] = style.getPropertyValue(prop_name)
            except Exception:
                pass

        return {"status": "ok", **info}


class SetStyleProperties(ToolBase):
    """Modify properties of an existing style or create a new one."""

    name = "set_style_properties"
    tier = "core"
    intent = "edit"
    description = (
        "Set properties on an existing style (font, size, margins, etc.). "
        "Can also create a new user-defined style. "
        "Works on all document types."
    )
    parameters = {
        "type": "object",
        "properties": {
            "style_name": {
                "type": "string",
                "description": "Style name to modify or create.",
            },
            "family": {
                "type": "string",
                "description": (
                    "Style family (e.g. ParagraphStyles, CharacterStyles). "
                    "Default: ParagraphStyles."
                ),
            },
            "create": {
                "type": "boolean",
                "description": (
                    "Create the style if it doesn't exist. "
                    "New styles are user-defined and based on the "
                    "parent_style or the family default."
                ),
            },
            "parent_style": {
                "type": "string",
                "description": (
                    "Parent style for a newly created style. "
                    "Default: the family's default style."
                ),
            },
            "properties": {
                "type": "object",
                "description": (
                    "Style properties to set. Keys are UNO property names "
                    "(e.g. CharFontName, CharHeight, ParaAdjust). "
                    "For margin properties ending in Margin, provide values in mm."
                ),
            },
        },
        "required": ["style_name", "properties"],
    }
    doc_types = None

    is_mutation = True

    # Properties whose values should be converted from mm to 1/100mm
    _MM_PROPS = {
        "ParaTopMargin",
        "ParaBottomMargin",
        "ParaLeftMargin",
        "ParaRightMargin",
    }

    def execute(self, ctx, **kwargs):
        style_name = kwargs.get("style_name", "")
        family = kwargs.get("family", "ParagraphStyles")
        create = kwargs.get("create", False)
        parent_style = kwargs.get("parent_style")
        properties = kwargs.get("properties", {})

        if not style_name:
            return {"status": "error", "message": "style_name is required."}
        if not properties:
            return {"status": "error", "message": "properties is required."}

        doc = ctx.doc
        families = doc.getStyleFamilies()

        if not families.hasByName(family):
            return {
                "status": "error",
                "message": "Unknown style family: %s" % family,
                "available_families": list(families.getElementNames()),
            }

        style_family = families.getByName(family)

        if style_family.hasByName(style_name):
            style = style_family.getByName(style_name)
        elif create:
            parent = parent_style or ""
            style = doc.createInstance("com.sun.star.style.Style")
            if parent and style_family.hasByName(parent):
                style.setParentStyle(parent)
            style_family.insertByName(style_name, style)
            style = style_family.getByName(style_name)
        else:
            return {
                "status": "error",
                "message": "Style '%s' not found in %s. Use create=true to define it."
                % (style_name, family),
            }

        applied = {}
        errors = []
        for prop_name, value in properties.items():
            try:
                if prop_name in self._MM_PROPS and isinstance(value, (int, float)):
                    value = int(value * 100)
                elif prop_name == "ParaLineSpacing" and isinstance(value, (int, float)):
                    from com.sun.star.style import LineSpacing, LineSpacingMode

                    ls = LineSpacing()
                    ls.Mode = LineSpacingMode.PROP
                    ls.Height = int(value * 100)
                    value = ls
                style.setPropertyValue(prop_name, value)
                applied[prop_name] = value
            except Exception as e:
                errors.append("%s: %s" % (prop_name, str(e)))

        result = {
            "status": "ok" if not errors else "partial",
            "style_name": style_name,
            "family": family,
            "applied": applied,
        }
        if errors:
            result["errors"] = errors
        return result
