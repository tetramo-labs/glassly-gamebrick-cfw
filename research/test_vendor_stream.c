#include <assert.h>
#include <string.h>
#include "../firmware/vendor_stream.h"
gb_u16 gb_test_connection;
gb_u32 gb_test_keys, gb_test_epoch;
static gb_u16 ccc;
static int result, count, handlers, change_during_send;
static gb_u8 captured[4];
gb_u16 gb_stock_ccc(gb_u16 connection, gb_u16 handle) {
  assert(connection == gb_test_connection); assert(handle == 0x55); return ccc;
}
int gb_stock_att(gb_u16 connection, gb_u16 handle, const gb_u8 *p, gb_u16 n, gb_u32 op) {
  assert(connection == gb_test_connection && handle == 0x54 && n == 4 && op == 0);
  memcpy(captured, p, 4); count++;
  if (change_during_send) gb_test_epoch++;
  return result;
}
void gb_stock_handler(void) { handlers++; }
int gb_stock_set_ccc(gb_u16 connection, gb_u16 handle, gb_u16 value) {
  assert(connection == gb_test_connection); if (handle == 0x55) ccc = value; return 17;
}
int gb_stock_ble_event(gb_u32 event, gb_u32 state, gb_u32 argument) {
  assert(event == 0x424c4500 && state == 7 && argument == 9); return 23;
}
static void keys(unsigned buttons) { gb_test_keys = ((buttons & 15) << 16) | ((buttons >> 4) & 3); }
int main(void) {
  struct gb_stream s = {0};
  assert(gb_poll(&s) == 0 && count == 0);
  gb_test_connection = 3;
  assert(gb_poll(&s) == 0 && count == 0);
  ccc = 1;
  assert(gb_poll(&s) == 1 && count == 1);
  assert(captured[0] == 0x47 && captured[1] == 1 && captured[2] == 0 && captured[3] == 0);
  assert(gb_poll(&s) == 0 && count == 1);
  keys(63); result = -100;
  assert(gb_poll(&s) == -100 && s.sequence == 1 && s.count == 1);
  keys(0); assert(gb_poll(&s) == -100 && s.count == 2);
  result = 0;
  assert(gb_poll(&s) == 1 && captured[2] == 1 && captured[3] == 63);
  assert(gb_poll(&s) == 1 && captured[3] == 0 && !s.count);
  assert(gb_poll(&s) == 0);
  /* Overflow retains the last 16 observed states and reports loss once. */
  result = -100;
  for (unsigned i = 1; i <= 40; i++) { keys(i & 1); assert(gb_poll(&s) == -100); }
  assert(s.count == 16 && s.overflow == GB_OVERFLOW);
  result = 0;
  for (unsigned i = 25; i <= 40; i++) {
    assert(gb_poll(&s) == 1);
    assert(captured[3] == ((i & 1) | (i == 25 ? GB_OVERFLOW : 0)));
  }
  assert(!s.count && gb_poll(&s) == 0);
  /* Unsubscribe/resubscribe between polls must still force a baseline. */
  assert(gb_ccc_changed(3, 0x55, 0) == 17);
  assert(gb_ccc_changed(3, 0x55, 1) == 17);
  assert(gb_poll(&s) == 1 && captured[3] == 0);
  assert(gb_ccc_changed(3, 0x28, 1) == 17);
  assert(gb_poll(&s) == 0);
  assert(gb_ble_changed(0x424c4500, 7, 9) == 23);
  assert(gb_poll(&s) == 1);
  gb_test_connection = 4; assert(gb_poll(&s) == 1);
  s.sequence = 255; keys(16);
  assert(gb_poll(&s) == 1 && captured[2] == 255 && s.sequence == 0);
  change_during_send = 1; keys(0);
  assert(gb_poll(&s) == 1 && !s.ready && !s.count);
  change_during_send = 0;
  assert(gb_poll(&s) == 1 && captured[3] == 0);
  ccc = 0; assert(gb_poll(&s) == 0 && !s.ready);
  ccc = 1; assert(gb_poll(&s) == 1);
  gb_tick(&s); assert(handlers == 1);
  gb_test_connection = 0; assert(gb_poll(&s) == 0 && !s.ready);
  return 0;
}
