# Copyright (c) David Berlioz
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Programmatic sidebar panel layout helpers.

Creates UNO container windows and controls without XDL files, avoiding
cross-VCL-backend rendering issues (GTK vs Qt vs Win32).
"""


def create_panel_window(ctx, parent_window):
    """Create a UnoControlContainer peered to *parent_window*.

    Returns a container that supports ``addControl()`` / ``getControl()``,
    equivalent to what ``ContainerWindowProvider.createContainerWindow()``
    returns from an XDL file.
    """
    smgr = ctx.getServiceManager()
    model = smgr.createInstanceWithContext(
        "com.sun.star.awt.UnoControlContainerModel", ctx)

    # Use the system dialog background color; -1 renders black on Windows
    try:
        cfg_prov = smgr.createInstanceWithContext(
            "com.sun.star.configuration.ConfigurationProvider", ctx)
        import uno
        from com.sun.star.beans import PropertyValue
        arg = PropertyValue()
        arg.Name = "nodepath"
        arg.Value = "/org.openoffice.Office.UI/ColorScheme"
        cfg = cfg_prov.createInstanceWithArguments(
            "com.sun.star.configuration.ConfigurationAccess", (arg,))
        scheme_name = cfg.getPropertyValue("CurrentColorScheme")
        schemes = cfg.getByName("ColorSchemes")
        scheme = schemes.getByName(scheme_name)
        bg_color = scheme.getPropertyValue("DialogColor")
        model.BackgroundColor = bg_color
    except Exception:
        # Fallback: standard light gray background
        model.BackgroundColor = 0xF0F0F0

    container = smgr.createInstanceWithContext(
        "com.sun.star.awt.UnoControlContainer", ctx)
    container.setModel(model)

    toolkit = smgr.createInstanceWithContext(
        "com.sun.star.awt.Toolkit", ctx)
    container.createPeer(toolkit, parent_window)

    container.setVisible(True)
    parent_rect = parent_window.getPosSize()
    if parent_rect.Width > 0 and parent_rect.Height > 0:
        container.setPosSize(
            0, 0, parent_rect.Width, parent_rect.Height, 15)

    return container


def add_control(ctx, container, name, service_name, model_props=None):
    """Add a named control to *container*.

    *service_name* is the short UNO control type, e.g. ``"Edit"``,
    ``"FixedText"``, ``"Button"``.  Creates the matching
    ``UnoControl<service_name>Model`` + ``UnoControl<service_name>``.

    Returns ``(control, model)`` tuple.
    """
    smgr = ctx.getServiceManager()
    model = smgr.createInstanceWithContext(
        "com.sun.star.awt.UnoControl%sModel" % service_name, ctx)
    if model_props:
        for k, v in model_props.items():
            setattr(model, k, v)

    ctrl = smgr.createInstanceWithContext(
        "com.sun.star.awt.UnoControl%s" % service_name, ctx)
    ctrl.setModel(model)
    container.addControl(name, ctrl)
    return ctrl, model
