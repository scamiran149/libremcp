# Copyright (c) David Berlioz
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Dialog utilities for LibreOffice UNO.

Provides helpers for message boxes, clipboard operations, and the about dialog.
"""

import logging

log = logging.getLogger("libremcp.dialogs")


# ── Simple message box ──────────────────────────────────────────────


def msgbox(ctx, title, message):
    """Show an info message box."""
    if not ctx:
        log.info("MSGBOX (no ctx) - %s: %s", title, message)
        return
    try:
        smgr = ctx.ServiceManager
        desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
        frame = desktop.getCurrentFrame()
        if frame is None:
            log.info("MSGBOX (no frame) - %s: %s", title, message)
            return
        window = frame.getContainerWindow()
        toolkit = smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
        box = toolkit.createMessageBox(window, 1, 1, title, message)
        box.execute()
    except Exception:
        log.exception("MSGBOX fallback - %s: %s", title, message)


# ── Clipboard ────────────────────────────────────────────────────────


def copy_to_clipboard(ctx, text):
    """Copy text to system clipboard via LO API. Returns True on success."""
    if not ctx:
        return False
    try:
        import uno
        import unohelper
        from com.sun.star.datatransfer import XTransferable, DataFlavor

        smgr = ctx.ServiceManager
        clip = smgr.createInstanceWithContext(
            "com.sun.star.datatransfer.clipboard.SystemClipboard", ctx
        )

        class _TextTransferable(unohelper.Base, XTransferable):
            def __init__(self, txt):
                self._text = txt

            def getTransferData(self, flavor):
                return self._text

            def getTransferDataFlavors(self):
                f = DataFlavor()
                f.MimeType = "text/plain;charset=utf-16"
                f.HumanPresentableName = "Unicode Text"
                f.DataType = uno.getTypeByName("string")
                return (f,)

            def isDataFlavorSupported(self, flavor):
                return "text/plain" in flavor.MimeType

        clip.setContents(_TextTransferable(text), None)
        return True
    except Exception:
        log.exception("Clipboard copy failed")
        return False


# ── About dialog ─────────────────────────────────────────────────────


def _find_logo_url():
    """Resolve the logo.png URL inside the installed extension."""
    try:
        import uno

        pip = uno.getComponentContext().getByName(
            "/singletons/com.sun.star.deployment.PackageInformationProvider"
        )
        ext_url = pip.getPackageLocation("org.extension.libremcp")
        if ext_url:
            return ext_url + "/assets/logo.png"
    except Exception:
        pass
    return ""


def about_dialog(ctx):
    """Show the LibreMCP About dialog with logo and clickable GitHub link."""
    try:
        from plugin.version import EXTENSION_VERSION
    except ImportError:
        EXTENSION_VERSION = "?"

    if not ctx:
        log.info("ABOUT (no ctx)")
        return

    _GITHUB_URL = "https://github.com/scamiran149/libremcp"

    try:
        smgr = ctx.ServiceManager

        dlg_model = smgr.createInstanceWithContext(
            "com.sun.star.awt.UnoControlDialogModel", ctx
        )
        dlg_model.Title = "About LibreMCP"
        dlg_model.Width = 240
        dlg_model.Height = 110

        logo_url = _find_logo_url()
        if logo_url:
            img = dlg_model.createInstance(
                "com.sun.star.awt.UnoControlImageControlModel"
            )
            img.Name = "Logo"
            img.PositionX = 10
            img.PositionY = 8
            img.Width = 40
            img.Height = 40
            img.ImageURL = logo_url
            img.ScaleImage = True
            img.Border = 0
            dlg_model.insertByName("Logo", img)

        text_x = 56 if logo_url else 10

        lbl = dlg_model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        lbl.Name = "Info"
        lbl.PositionX = text_x
        lbl.PositionY = 8
        lbl.Width = 230 - text_x
        lbl.Height = 36
        lbl.MultiLine = True
        lbl.Label = (
            "LibreMCP\nVersion: %s\nMCP server for LibreOffice" % EXTENSION_VERSION
        )
        dlg_model.insertByName("Info", lbl)

        link = dlg_model.createInstance(
            "com.sun.star.awt.UnoControlFixedHyperlinkModel"
        )
        link.Name = "GitHubLink"
        link.PositionX = text_x
        link.PositionY = 52
        link.Width = 230 - text_x
        link.Height = 12
        link.Label = "GitHub: scamiran149/libremcp"
        link.URL = _GITHUB_URL
        link.TextColor = 0x0563C1
        dlg_model.insertByName("GitHubLink", link)

        ok_btn = dlg_model.createInstance("com.sun.star.awt.UnoControlButtonModel")
        ok_btn.Name = "OKBtn"
        ok_btn.PositionX = 180
        ok_btn.PositionY = 88
        ok_btn.Width = 50
        ok_btn.Height = 14
        ok_btn.Label = "OK"
        ok_btn.PushButtonType = 1
        dlg_model.insertByName("OKBtn", ok_btn)

        dlg = smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialog", ctx)
        dlg.setModel(dlg_model)
        toolkit = smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
        dlg.createPeer(toolkit, None)
        dlg.execute()
        dlg.dispose()
    except Exception:
        log.exception("About dialog error")
        msgbox(
            ctx,
            "About LibreMCP",
            "LibreMCP %s\n%s" % (EXTENSION_VERSION, _GITHUB_URL),
        )
