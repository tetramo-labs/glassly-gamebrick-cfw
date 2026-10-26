/* Exact-version task trampolines. See docs/custom-firmware.md. */
.text
.globl gb_task_entry
.p2align 1
.type gb_task_entry,@function
gb_task_entry:
  /* This is the task-create entry. Reserve 40 bytes before the stock 88-byte frame. */
  sp += -40
  r0 = 0
  [sp] = r0
  [sp+4] = r0
  [sp+8] = r0
  [sp+12] = r0
  [sp+16] = r0
  [sp+20] = r0
  [sp+24] = r0
  [sp+28] = r0
  [sp+32] = r0
  [sp+36] = r0
  goto gb_stock_task_entry
.size gb_task_entry, .-gb_task_entry

.globl gb_task_tick
.p2align 1
.type gb_task_tick,@function
gb_task_tick:
  /* No frame yet: sp belongs to the calling task. Tail call retains rets. */
  r0 = sp + 88
  goto gb_tick
.size gb_task_tick, .-gb_task_tick

.globl gb_ble_tail
.p2align 1
.type gb_ble_tail,@function
gb_ble_tail:
  /* Replaces a two-byte call plus the original state-function epilogue. */
  call gb_ble_changed
  {pc, r6-r4} = [sp++]
.size gb_ble_tail, .-gb_ble_tail
