/* Small compiler-generated references for Q32S decoder/ABI validation. */
typedef unsigned int u32;
extern u32 opaque(u32,u32,u32,u32,u32);
u32 shift_left(u32 x,u32 n) { return x<<n; }
u32 shift_right(u32 x,u32 n) { return x>>n; }
u32 arithmetic_right(int x,u32 n) { return x>>n; }
u32 left16(u32 x) { return x<<16; }
u32 right8(u32 x) { return x>>8; }
u32 leading_zeros(u32 x) { return __builtin_clz(x); }
u32 preserve(u32 a,u32 b,u32 c,u32 d,u32 e) { u32 x=opaque(a,b,c,d,e);return a+b+c+d+e+x; }
u32 call_five(u32 a) { return opaque(a,2,3,4,5); }
u32 bitfield(u32 x) { return (x>>3)&0x1f; }
u32 signed_field(int x) { return (x<<24)>>24; }
