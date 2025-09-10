import libcst as cst
import libcst.matchers as m

class ShellArgFixer(cst.CSTTransformer):
    """
    subprocess.*(..., shell=True, ...) -> enforce shell=False
    os.system(cmd) -> subprocess.run([cmd], shell=False, check=True)
    """
    def leave_Call(self, original_node: cst.Call, updated_node: cst.Call):
        fname = cst.helpers.get_full_name_for_node(updated_node.func) or ""

        # Fix subprocess.* shell=True -> False
        if fname.startswith("subprocess."):
            args = list(updated_node.args)
            changed = False
            for i, a in enumerate(args):
                if a.keyword and a.keyword.value == "shell" and m.matches(a.value, m.Name("True")):
                    args[i] = a.with_changes(value=cst.Name("False"))
                    changed = True
            if changed:
                return updated_node.with_changes(args=args)

        # Rewrite os.system(cmd) -> subprocess.run([cmd], shell=False, check=True)
        if fname == "os.system" and len(updated_node.args) >= 1:
            cmd_expr = updated_node.args[0].value
            new_call = cst.Call(
                func=cst.Attribute(value=cst.Name("subprocess"), attr=cst.Name("run")),
                args=[
                    cst.Arg(value=cst.List([cmd_expr])),
                    cst.Arg(keyword=cst.Name("shell"), value=cst.Name("False")),
                    cst.Arg(keyword=cst.Name("check"), value=cst.Name("True")),
                ],
            )
            return new_call

        return updated_node


class YamlSafeLoadFixer(cst.CSTTransformer):
    """
    yaml.load(...) -> yaml.safe_load(...)
    """
    def leave_Call(self, original_node: cst.Call, updated_node: cst.Call):
        fname = cst.helpers.get_full_name_for_node(updated_node.func) or ""
        if fname == "yaml.load":
            return updated_node.with_changes(
                func=cst.Attribute(value=cst.Name("yaml"), attr=cst.Name("safe_load"))
            )
        return updated_node


class EvalExecGuard(cst.CSTTransformer):
    """
    Replace eval/exec with ast.literal_eval where applicable.
    (Note: Real projects may need a more nuanced strategy and additional imports.)
    """
    def leave_Call(self, original_node: cst.Call, updated_node: cst.Call):
        fname = cst.helpers.get_full_name_for_node(updated_node.func) or ""
        if fname in {"eval", "exec"}:
            return updated_node.with_changes(
                func=cst.Attribute(value=cst.Name("ast"), attr=cst.Name("literal_eval"))
            )
        return updated_node


def auto_repair(code: str) -> str:
    try:
        mod = cst.parse_module(code)
        for t in [ShellArgFixer(), YamlSafeLoadFixer(), EvalExecGuard()]:
            mod = mod.visit(t)
        return mod.code
    except Exception:
        return code