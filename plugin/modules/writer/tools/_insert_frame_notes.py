# Notes on TextFrame + image insertion approaches.
#
# mcp-libre approach (current — simple, proven):
#   - Frame size = image size (auto-grows for caption)
#   - No custom margins, borders, SizeType
#   - Image: AnchorType=0 (AT_PARAGRAPH), HoriOrient=2 (CENTER), VertOrient=1 (TOP)
#   - insertTextContent(frame_cursor, graphic, False)
#   - Caption via insertControlCharacter + insertString
#
# Custom approach (kept for reference — tried to match document's existing frames):
#   - Frame size = image + caption_height
#   - Zero margins, no borders
#   - Image: AnchorType=0, HoriOrient=0, VertOrient=0
#   - SizeType=2, WidthType=1
#   - Tried to remove initial empty paragraph
#   - Had issues: image wider than frame, empty line above image
#
# Reference frame properties (from existing document "Cadre4"):
#   AnchorType: AT_CHARACTER
#   HoriOrient: 0 (NONE)
#   VertOrient: 0 (NONE)
#   LeftMargin: 499, RightMargin: 499, TopMargin: 0, BottomMargin: 499
#   SizeType: 2, WidthType: 1
#   Image inside: AnchorType=AT_PARAGRAPH, HoriOrient=0, VertOrient=0
