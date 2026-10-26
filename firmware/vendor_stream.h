#ifndef GAMEBRICK_VENDOR_STREAM_H
#define GAMEBRICK_VENDOR_STREAM_H
#include "input_state.h"
#define GB_QUEUE_CAPACITY 16u
#define GB_OVERFLOW 0x40u
/* Persistent task-stack storage, cleared by gb_task_entry. Only the task owns it. */
struct gb_stream {
  gb_u32 epoch;
  gb_u16 connection;
  gb_u8 sequence, ready, observed, head, count, overflow;
  gb_u8 queue[GB_QUEUE_CAPACITY];
};
typedef char gb_state_fits_task_slot[sizeof(struct gb_stream) <= 40 ? 1 : -1];
/* Accepted snapshot: 1; idle: 0; stock transmit error: negative. */
int gb_poll(struct gb_stream *state);
void gb_tick(struct gb_stream *state);
int gb_ccc_changed(gb_u16 connection, gb_u16 handle, gb_u16 value);
int gb_ble_changed(gb_u32 event, gb_u32 state, gb_u32 argument);
#endif
