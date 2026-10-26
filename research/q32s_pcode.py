"""Strict interpreter for the P-code subset used by the recovered GPIO scan.
Not a Q32S hardware emulator. Unknown operations, addresses and calls stop execution.
"""
from pathlib import Path
import pypcode
ROOT=Path(__file__).resolve().parent
class Machine:
 def __init__(self):
  arch=pypcode.Arch('Jieli',str(ROOT/'q32s-analysis/processor/data/languages/JieLi.ldefs'))
  self.ctx=pypcode.Context(next(x for x in arch.languages if x.id=='q32s:LE:32:default'))
  self.app=(ROOT/'unpacked/files/app.bin').read_bytes();self.mem={};self.calls=[]
 def read(self,space,addr,size):
  if space=='const':return addr
  return sum(self.mem.get((space,addr+i),0)<<(8*i) for i in range(size))
 def write(self,space,addr,size,val):
  if space=='ram' and not 0<=addr<=0xc000-size:raise ValueError('Unexpected RAM address')
  for i in range(size):self.mem[space,addr+i]=(val>>(i*8))&255
 def reg(self,name,value=None):
  r=self.ctx.registers[name]
  if value is None:return self.read('register',r.offset,r.size)
  self.write('register',r.offset,r.size,value)
 def value(self,node):return self.read(node.space.name,node.offset,node.size)
 @staticmethod
 def signed(value,size):
  sign=1<<(8*size-1);return (value^sign)-sign
 def before_instruction(self,pc):
  """Optional fetch validation for bounded hardware-protection regressions."""
  pass
 def execute(self,pc,stop,gpio_high=0xffffffff,max_steps=1000):
  count=0
  while pc!=stop:
   count+=1
   if count>max_steps:raise ValueError('Instruction bound exceeded')
   self.before_instruction(pc)
   off=pc-0x1e00120
   if not 0<=off<len(self.app):raise ValueError(f'Unexpected code address {pc:x}')
   ins=self.ctx.disassemble(self.app[off:off+16],pc,max_instructions=1).instructions[0]
   ops=self.ctx.translate(self.app[off:off+16],pc,max_instructions=1).ops
   next_pc=pc+ins.length;j=0
   while j<len(ops):
    op=ops[j];name=op.opcode.name;v=[self.value(x) for x in op.inputs];result=None
    if name=='IMARK':pass
    elif name=='COPY':result=v[0]
    elif name=='LOAD':result=self.read('ram',v[1],op.output.size)
    elif name=='STORE':self.write('ram',v[1],op.inputs[2].size,v[2])
    elif name=='INT_ADD':result=v[0]+v[1]
    elif name=='INT_SUB':result=v[0]-v[1]
    elif name=='INT_OR':result=v[0]|v[1]
    elif name=='INT_AND':result=v[0]&v[1]
    elif name=='INT_XOR':result=v[0]^v[1]
    elif name=='INT_NEGATE':result=~v[0]
    elif name=='INT_LEFT':result=v[0]<<v[1] if v[1]<64 else 0
    elif name=='INT_RIGHT':result=v[0]>>v[1]
    elif name=='INT_SRIGHT':result=self.signed(v[0],op.inputs[0].size)>>v[1]
    elif name=='INT_ZEXT':result=v[0]
    elif name=='INT_SEXT':result=self.signed(v[0],op.inputs[0].size)
    elif name=='INT_EQUAL':result=int(v[0]==v[1])
    elif name=='INT_NOTEQUAL':result=int(v[0]!=v[1])
    elif name=='INT_LESS':result=int(v[0]<v[1])
    elif name=='INT_LESSEQUAL':result=int(v[0]<=v[1])
    elif name=='INT_SLESS':result=int(self.signed(v[0],op.inputs[0].size)<self.signed(v[1],op.inputs[1].size))
    elif name=='INT_SLESSEQUAL':result=int(self.signed(v[0],op.inputs[0].size)<=self.signed(v[1],op.inputs[1].size))
    elif name=='BOOL_NEGATE':result=int(not v[0])
    elif name=='SUBPIECE':result=v[0]>>(8*v[1])
    elif name in ('BRANCH','CBRANCH'):
     if name=='BRANCH' or v[1]:
      target=op.inputs[0]
      if target.space.name=='const':j+=self.signed(target.offset,target.size);continue
      next_pc=target.offset;break
    elif name=='CALL':
     next_pc=self.call(op.inputs[0].offset,next_pc,gpio_high);break
    elif name in ('RETURN','BRANCHIND'):
     next_pc=v[0];break
    else:raise ValueError(f'Unsupported P-code at {pc:x}: {op}')
    if result is not None:self.write(op.output.space.name,op.output.offset,op.output.size,result)
    j+=1
   pc=next_pc
  return count

 def call(self,target,next_pc,gpio_high):
  if target!=0x4b1a:raise ValueError(f'Unexpected call {target:x}')
  pin=self.reg('r0');self.calls.append(pin)
  if pin not in (19,7,22,23,0,24,25):raise ValueError('Unexpected GPIO')
  self.reg('r0',(gpio_high>>pin)&1);self.reg('rets',next_pc)
  for name in ('r1','r2','r3'):self.reg(name,0xa5a5a5a5)
  return next_pc
