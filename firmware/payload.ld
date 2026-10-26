/* Exact-version development payload. Packaging applies all required hooks. */
ENTRY(gb_task_entry)
gb_stock_ccc = 0x01e041b6;
gb_stock_att = 0x01e034b4;
gb_stock_handler = 0x01e0ce10;
gb_stock_set_ccc = 0x01e14114;
gb_stock_ble_event = 0x01e0520c;
gb_stock_task_entry = 0x01e0ee68;
SECTIONS {
  . = 0x01e309d0;
  .text : { KEEP(*(.text)) KEEP(*(.text.gb_ccc_changed)) KEEP(*(.text.gb_ble_changed)) *(.text*) *(.rodata*) }
  .data : { *(.data*) }
  .bss : { *(.bss*) *(COMMON) }
  /DISCARD/ : { *(.comment) *(.note*) *(.eh_frame*) }
}
ASSERT(SIZEOF(.data) == 0, "Payload must not require initialized data")
ASSERT(SIZEOF(.bss) == 0, "Payload must not allocate unplaced BSS")
ASSERT(SIZEOF(.text) < 0x1000, "Unexpected payload growth")
