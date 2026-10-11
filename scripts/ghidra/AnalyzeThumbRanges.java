// @category EXE6
// Args: tab-separated start, end-exclusive, name file; output report.
import ghidra.app.script.GhidraScript;
import ghidra.app.cmd.disassemble.DisassembleCommand;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressSet;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.mem.MemoryBlock;
import java.math.BigInteger;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;

public class AnalyzeThumbRanges extends GhidraScript {
    public void run() throws Exception {
        MemoryBlock[] blocks = currentProgram.getMemory().getBlocks();
        if (blocks.length != 1 || blocks[0].getSize() != 0x800000L) {
            throw new IllegalStateException("Expected one 8 MiB ROM block");
        }
        if (!blocks[0].getStart().equals(currentProgram.getImageBase())) {
            currentProgram.getMemory().moveBlock(blocks[0], currentProgram.getImageBase(), monitor);
        }
        currentProgram.setImageBase(toAddr(0x08000000L), true);
        ArrayList<Function> functions = new ArrayList<>();
        StringBuilder report = new StringBuilder("Language: " + currentProgram.getLanguageID() + "\n");
        for (String line : Files.readAllLines(Path.of(getScriptArgs()[0]))) {
            if (line.isBlank() || line.startsWith("#")) continue;
            String[] fields = line.split("\\s+");
            Address entry = toAddr(Long.decode(fields[0]));
            Address end = toAddr(Long.decode(fields[1]) - 1);
            AddressSet code = new AddressSet(entry, end);
            currentProgram.getProgramContext().setValue(currentProgram.getRegister("TMode"), entry, end, BigInteger.ONE);
            if (!new DisassembleCommand(entry, code, true).applyTo(currentProgram, monitor)) {
                throw new IllegalStateException("Disassembly failed at " + entry);
            }
            Function function = createFunction(entry, fields[2]);
            if (function == null) throw new IllegalStateException("Function creation failed at " + entry);
            functions.add(function);
            report.append("\n").append(fields[2]).append(" ").append(code).append('\n');
            for (Instruction instruction : currentProgram.getListing().getInstructions(code, true)) {
                report.append(instruction.getAddress()).append("  ").append(instruction).append('\n');
            }
        }
        DecompInterface decompiler = new DecompInterface();
        try {
            if (!decompiler.openProgram(currentProgram)) throw new IllegalStateException("Decompiler open failed");
            for (Function function : functions) {
                DecompileResults result = decompiler.decompileFunction(function, 30, monitor);
                report.append("\nDecompiler: ").append(function.getName()).append('\n');
                if (!result.decompileCompleted()) throw new IllegalStateException(result.getErrorMessage());
                report.append(result.getDecompiledFunction().getC());
            }
        } finally { decompiler.dispose(); }
        Files.writeString(Path.of(getScriptArgs()[1]), report.toString());
        println("Exported " + functions.size() + " functions to " + getScriptArgs()[1]);
    }
}
