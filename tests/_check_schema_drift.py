"""One-off script to verify @tool schemas match function signatures."""
import sys
sys.path.insert(0, "src")

from sciagent.tools.registry import verify_tool_schemas
from patchagent.tools import io_tools, spike_tools, passive_tools, qc_tools, fitting_tools, code_tools

errors = verify_tool_schemas(io_tools, spike_tools, passive_tools, qc_tools, fitting_tools, code_tools)

if errors:
    print("MISMATCHES FOUND:")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)
else:
    from sciagent.tools.registry import collect_tools
    total = sum(len(list(collect_tools(m))) for m in [io_tools, spike_tools, passive_tools, qc_tools, fitting_tools, code_tools])
    print(f"All tools validated - 0 schema/signature mismatches across {total} tools in 6 modules")
