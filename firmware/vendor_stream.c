#include "vendor_stream.h"
#ifdef GB_HOST_TEST
extern gb_u16 gb_test_connection;
extern gb_u32 gb_test_keys, gb_test_epoch;
#define CONNECTION gb_test_connection
#define KEYS gb_test_keys
#define EPOCH gb_test_epoch
#else
#define CONNECTION (*(volatile gb_u16 *)0x29e2u)
#define KEYS (*(volatile gb_u32 *)0x2a78u)
/* Four bytes reserved by extending startup BSS clearing to 0x40bc. */
#define EPOCH (*(volatile gb_u32 *)0x40b8u)
#endif
extern gb_u16 gb_stock_ccc(gb_u16 connection, gb_u16 handle);
extern int gb_stock_att(gb_u16 connection, gb_u16 handle, const gb_u8 *packet,
                       gb_u16 length, gb_u32 operation);
extern void gb_stock_handler(void);
extern int gb_stock_set_ccc(gb_u16 connection, gb_u16 handle, gb_u16 value);
extern int gb_stock_ble_event(gb_u32 event, gb_u32 state, gb_u32 argument);

int gb_poll(struct gb_stream *s) {
  gb_u8 packet[4];
  gb_u32 epoch = EPOCH;
  gb_u16 connection = CONNECTION;
  gb_u8 buttons;
  int result;
  if (!connection || !(gb_stock_ccc(connection, 0x55) & 1u) || epoch != EPOCH) {
    s->ready = 0;
    s->count = 0;
    return 0;
  }
  buttons = gb_compact_keys(KEYS);
  if (!s->ready || s->connection != connection || s->epoch != epoch) {
    s->epoch = epoch;
    s->connection = connection;
    s->head = 0;
    s->count = 1;
    s->queue[0] = buttons;
    s->observed = buttons;
    s->overflow = 0;
    s->ready = 1;
  } else if (s->observed != buttons) {
    s->observed = buttons;
    if (s->count == GB_QUEUE_CAPACITY) {
      /* Drop the oldest unsent state; retain the latest release and flag loss. */
      s->head = (s->head + 1u) & (GB_QUEUE_CAPACITY - 1u);
      s->count--;
      s->overflow = GB_OVERFLOW;
    }
    s->queue[(s->head + s->count) & (GB_QUEUE_CAPACITY - 1u)] = buttons;
    s->count++;
  }
  if (!s->count) return 0;
  packet[0] = 0x47;
  packet[1] = 1;
  packet[2] = s->sequence;
  packet[3] = s->queue[s->head] | s->overflow;
  /* Bind to the checked connection, rather than rereading a global in AE42's wrapper. */
  result = gb_stock_att(connection, 0x54, packet, sizeof packet, 0);
  if (epoch != EPOCH || connection != CONNECTION) {
    s->ready = 0;
    s->count = 0;
  } else if (!result) {
    s->head = (s->head + 1u) & (GB_QUEUE_CAPACITY - 1u);
    s->count--;
    s->overflow = 0;
  }
  if (result) return result;
  s->sequence++;
  return 1;
}

void gb_tick(struct gb_stream *s) {
  gb_stock_handler();
  (void)gb_poll(s);
}

/* Both call sites execute on the stock Bluetooth event path. No queue access here. */
int gb_ccc_changed(gb_u16 connection, gb_u16 handle, gb_u16 value) {
  int result = gb_stock_set_ccc(connection, handle, value);
  if (handle == 0x55) EPOCH++;
  return result;
}
int gb_ble_changed(gb_u32 event, gb_u32 state, gb_u32 argument) {
  int result = gb_stock_ble_event(event, state, argument);
  EPOCH++;
  return result;
}
