# Elecrow 2.13-inch display driver

These seven driver and font files are copied unchanged from Elecrow's official
CrowPanel 2.13-inch arduino-v1.2 example (JD79661 controller). Original comments are preserved.

- Source: https://github.com/Elecrow-RD/CrowPanel-ESP32-2.13-E-paper-HMI-Display-with-122-250
- Commit: `11291e3e9a868be8943232b065f3e264dfaeeae3`
- Directory: `example/arduino-v1.2/main`
- Files: `EPD.cpp`, `EPD.h`, `EPD_Init.cpp`, `EPD_Init.h`, `EPDfont.h`, `spi.cpp`, `spi.h`.

The vendor uses a 250 x 128 padded framebuffer for the 250 x 122 visible panel.
Drawing sets bits for black; this revision transfers bytes without inversion.
The application uses its own layout renderer in `tools/render.py` and `firmware/include/panel_canvas.h`, which
writes the final controller byte format directly (1 = white, 0 = black),
accounting for the JD79661 scan direction. Vendor drawing helpers are unused.
Use the JD79661 `EPD_Clear`, `EPD_DisplayImage`, and `EPD_Update` sequence.
Some retained vendor helpers target the older SSD1680 controller and are unused.
