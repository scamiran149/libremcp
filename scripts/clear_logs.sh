#!/bin/bash
# Clear all LibreMCP log files in every known location.
# Filenames: libremcp_debug.log, libremcp_agent.log (see core/logging.py).

LO="${HOME}/.config/libreoffice"
rm -f \
  "${HOME}/libremcp_debug.log" \
  "${HOME}/libremcp_agent.log" \
  "${LO}/4/user/libremcp_debug.log" \
  "${LO}/4/user/libremcp_agent.log" \
  "${LO}/4/user/config/libremcp_debug.log" \
  "${LO}/4/user/config/libremcp_agent.log" \
  "${LO}/24/user/libremcp_debug.log" \
  "${LO}/24/user/libremcp_agent.log" \
  "${LO}/24/user/config/libremcp_debug.log" \
  "${LO}/24/user/config/libremcp_agent.log"
echo "Logs deleted."
