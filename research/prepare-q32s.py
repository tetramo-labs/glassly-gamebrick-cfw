"""Build an isolated analysis-only Q32S specification with documented corrections."""
from pathlib import Path
import shutil,re,subprocess,json,hashlib
root=Path(__file__).resolve().parent
src=root/'ghidra-jieli'
out=root/'q32s-analysis/processor'
shutil.copytree(src,out,dirs_exist_ok=True,ignore=shutil.ignore_patterns('.git','*.sla'))
p=out/'data/languages/q32s_ins_progflow.sinc'
s=p.read_text()
# These constructors contradict their mnemonics and the matched C receive/parser code.
s,n1=re.subn(r'(:jls[^\n]*\n\{ if \([^\n]*) > ',r'\1 <= ',s)
s,n2=re.subn(r'(:jge[^\n]*\n\{ if \([^\n]*) s<= ',r'\1 s>= ',s)
assert (n1,n2)==(3,3),(n1,n2)
p.write_text(s)
p=out/'data/languages/q32s.slaspec';s=p.read_text()
# Long calls from flash to RAM/ROM wrap at the 25-bit code address boundary.
# Verified against BD19 maskrom_stubs.ld: memcpy/memset/strcmp/strlen targets.
old='res = ((addr0005s << 17) | (addr1631 << 1)) + inst_next;'
assert old in s
s=s.replace(old,'res = (((addr0005s << 17) | (addr1631 << 1)) + inst_next) & 0x1ffffff;')
p.write_text(s)
meta={'upstream_commit':subprocess.check_output(['git','-C',str(src),'rev-parse','HEAD'],text=True).strip(),'corrections':['jls unsigned <=, three forms','jge signed >=, three forms','25-bit long-call/jump address wrap'],'limits':['register-list push/pop semantics incomplete','undecoded instructions remain','function discovery heuristic; generated C is not ground truth']}
(root/'q32s-analysis/processor-corrections.json').write_text(json.dumps(meta,indent=2)+'\n')
print(out)
