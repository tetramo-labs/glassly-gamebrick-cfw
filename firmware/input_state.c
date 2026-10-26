#include "input_state.h"
/* Stock GPIO reads at 0x01e0ce4a..0x01e0cec4. Active low. */
gb_u32 gb_raw_keys(gb_u32 high) {
  gb_u32 keys = 0;
  if (!(high & (1u << 19))) keys |= 1u;          /* PB3: logical A */
  if (!(high & (1u << 7)))  keys |= 2u;          /* PA7: logical B */
  if (!(high & (1u << 22))) keys |= 0x80401000u; /* PB6: HOME/FN/POWER aliases */
  if (!(high & (1u << 23))) keys |= 1u << 16;    /* PB7: Up */
  if (!(high & (1u << 0)))  keys |= 1u << 17;    /* PA0: Down */
  if (!(high & (1u << 24))) keys |= 1u << 18;    /* PB8: Left */
  if (!(high & (1u << 25))) keys |= 1u << 19;    /* PB9: Right */
  return keys;
}
void gb_scan_step(struct gb_debounce *s, gb_u32 tick, gb_u32 high) {
  gb_u32 sample;
  if ((gb_u32)(tick - s->last_tick) < 100u) return;
  s->last_tick = tick;
  sample = gb_raw_keys(high);
  if (s->candidate == sample) s->stable = sample;
  else s->candidate = sample;
  if (s->keys != s->stable) s->keys = s->stable;
}
gb_u8 gb_compact_keys(gb_u32 keys) {
  return (gb_u8)(((keys >> 16) & 15u) | ((keys & 3u) << 4));
}
