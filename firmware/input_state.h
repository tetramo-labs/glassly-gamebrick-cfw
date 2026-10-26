#ifndef GAMEBRICK_INPUT_STATE_H
#define GAMEBRICK_INPUT_STATE_H
/* Freestanding types: the Q32S ABI uses 32-bit unsigned int. */
typedef unsigned int gb_u32;
typedef unsigned short gb_u16;
typedef unsigned char gb_u8;
struct gb_debounce { gb_u32 last_tick, candidate, stable, keys; };
/* Recovered stock algorithm; gpio_high has one bit per SDK GPIO number. */
gb_u32 gb_raw_keys(gb_u32 gpio_high);
void gb_scan_step(struct gb_debounce *state, gb_u32 tick, gb_u32 gpio_high);
/* New wire format: Up, Down, Left, Right, A, B in bits 0..5. */
gb_u8 gb_compact_keys(gb_u32 keys);
#endif
