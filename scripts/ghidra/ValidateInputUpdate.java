// Analyze only the known EXE6F input routine, without whole-ROM auto analysis.
// @category EXE6
import ghidra.app.script.GhidraScript;
import ghidra.app.cmd.disassemble.DisassembleCommand;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressSet;
import ghidra.program.model.data.DWordDataType;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.mem.MemoryBlock;
import java.math.BigInteger;
import java.nio.file.Files;
import java.nio.file.Path;

public class ValidateInputUpdate extends GhidraScript {
    public void run() throws Exception {
        // Raw Binary's baseAddr maps the block but may leave image-base
        // metadata at zero. Normalize before setting the program image base.
        MemoryBlock[] blocks = currentProgram.getMemory().getBlocks();
        if (blocks.length != 1 || blocks[0].getSize() != 0x800000L) {
            throw new IllegalStateException("Expected one 8 MiB ROM block");
        }
        if (!blocks[0].getStart().equals(currentProgram.getImageBase())) {
            currentProgram.getMemory().moveBlock(blocks[0], currentProgram.getImageBase(), monitor);
        }
        currentProgram.setImageBase(toAddr(0x08000000L), true);
        Address entry = toAddr(0x080003e4L);
        Address end = toAddr(0x08000449L);
        currentProgram.getProgramContext().setValue(
            currentProgram.getRegister("TMode"), entry, end, BigInteger.ONE);
        AddressSet code = new AddressSet(entry, end);
        if (!new DisassembleCommand(entry, code, true).applyTo(currentProgram, monitor)) {
            throw new IllegalStateException("Thumb disassembly failed");
        }
        Function function = createFunction(entry, "exe6f_update_input");
        if (function == null) throw new IllegalStateException("Function creation failed");
        createData(toAddr(0x0800044cL), DWordDataType.dataType);
        createData(toAddr(0x08000450L), DWordDataType.dataType);
        StringBuilder report = new StringBuilder();
        report.append("Language: ").append(currentProgram.getLanguageID()).append('\n');
        report.append("Image base: ").append(currentProgram.getImageBase()).append('\n');
        report.append("ROM block: ").append(blocks[0].getStart()).append("..")
              .append(blocks[0].getEnd()).append('\n');
        report.append("Function body: ").append(function.getBody()).append('\n');
        for (Instruction instruction : currentProgram.getListing().getInstructions(code, true)) {
            report.append(instruction.getAddress()).append("  ").append(instruction).append('\n');
        }
        report.append("Literal 0800044c: ").append(String.format("%08x", getInt(toAddr(0x0800044cL)))).append('\n');
        report.append("Literal 08000450: ").append(String.format("%08x", getInt(toAddr(0x08000450L)))).append('\n');
        DecompInterface decompiler = new DecompInterface();
        try {
            if (!decompiler.openProgram(currentProgram)) throw new IllegalStateException("Decompiler open failed");
            DecompileResults result = decompiler.decompileFunction(function, 30, monitor);
            if (!result.decompileCompleted()) throw new IllegalStateException(result.getErrorMessage());
            report.append("\nDecompiler output (untyped; not a semantic specification):\n");
            report.append(result.getDecompiledFunction().getC());
        } finally {
            decompiler.dispose();
        }
        Files.writeString(Path.of(getScriptArgs()[0]), report.toString());
        println(report.toString());
    }
}
