// Import and annotate the exact stock Gamebrick Q32S app. Generated C is advisory.
// @category Gamebrick
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.mem.*;
import ghidra.program.model.symbol.*;
import java.io.*;
import java.nio.file.*;
import java.security.*;
import java.util.*;

public class AnalyzeGamebrick extends GhidraScript {
 public void run() throws Exception {
  String[] args=getScriptArgs();
  byte[] bytes=Files.readAllBytes(Path.of(args[0]));
  String sha=HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
  if(!sha.equals("2fb44f4235bd4ed7183439f31ee2a31fb0052d19dd736e20d1d251fd5e1ff259")) throw new IOException("Unexpected application hash");
  Memory mem=currentProgram.getMemory();
  MemoryBlock ram=mem.createInitializedBlock("RAM",toAddr(0),0xc000,(byte)0,monitor,false);
  ram.setWrite(true); ram.setExecute(true);
  // Startup copies, recovered from 0x01e0016c and 0x01e00192.
  mem.setBytes(toAddr(0x840),bytes,0x2dea8,0xc60);
  mem.setBytes(toAddr(0x40c0),bytes,0x2eb08,0x1d88);
  // Only seed call candidates whose destination begins with a recognized prologue.
  for(String line:Files.readAllLines(Path.of(args[1]))) {
   if(line.isBlank()) continue;
   String[] parts=line.split(" ",2); Address a=toAddr(Long.parseLong(parts[0],16));
   disassemble(a); Function f=getFunctionAt(a);
   if(f==null) f=createFunction(a,parts.length>1?parts[1]:null);
   else if(parts.length>1) f.setName(parts[1],SourceType.USER_DEFINED);
  }
  // ROM stubs are named from the pinned SDK, without inventing ROM contents.
  mem.createUninitializedBlock("MASKROM",toAddr(0x100000),0x10000,false);
  for(String line:Files.readAllLines(Path.of(args[3]))) {
   java.util.regex.Matcher m=java.util.regex.Pattern.compile("\\s*(\\w+) = ABSOLUTE\\(0x([0-9a-fA-F]+)\\);").matcher(line);
   if(m.matches()) {Address a=toAddr(Long.parseLong(m.group(2),16)); createLabel(a,m.group(1),true);}
  }
  analyzeAll(currentProgram);
  Path out=Path.of(args[2]); Files.createDirectories(out);
  DecompInterface decomp=new DecompInterface(); decomp.openProgram(currentProgram);
  try(PrintWriter functions=new PrintWriter(out.resolve("functions.tsv").toFile());
      PrintWriter c=new PrintWriter(out.resolve("decompiled.c").toFile());
      PrintWriter asm=new PrintWriter(out.resolve("listing.txt").toFile())) {
   functions.println("address\tname\tsize\tdecompiled");
   c.println("/* Q32S analysis output; incomplete SLEIGH semantics. NOT rebuildable source. */");
   FunctionIterator it=currentProgram.getFunctionManager().getFunctions(true);
   while(it.hasNext()&&!monitor.isCancelled()) {
    Function f=it.next();
    DecompileResults result=decomp.decompileFunction(f,15,monitor);
    functions.printf("%s\t%s\t%d\t%b%n",f.getEntryPoint(),f.getName(),f.getBody().getNumAddresses(),result.decompileCompleted());
    c.printf("\n/* %s %s */\n",f.getEntryPoint(),f.getName());
    if(result.decompileCompleted()) c.println(result.getDecompiledFunction().getC());
    else c.println("/* "+result.getErrorMessage()+" */");
   }
   InstructionIterator instructions=currentProgram.getListing().getInstructions(true);
   while(instructions.hasNext()) {Instruction i=instructions.next();asm.println(i.getAddress()+" "+i);}
  } finally {decomp.dispose();}
  println("Gamebrick exports: "+out);
 }
}
