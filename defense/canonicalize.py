import argparse
import pathlib
import libcst as cst
import libcst.matchers as m

class ImportAliasNormalizer(cst.CSTTransformer):
    """
    - Normalize import aliases: `import os as o` -> `import os`
    - Normalize from-import aliases: `from subprocess import run as r` -> `from subprocess import run`
    - Rewrite alias references back to original names
    """
    def __init__(self):
        self.alias_map = {}

    def leave_ImportAlias(self, original_node: cst.ImportAlias, updated_node: cst.ImportAlias):
        if original_node.asname:
            orig = cst.helpers.get_full_name_for_node(original_node.name)
            alias = original_node.asname.name.value
            self.alias_map[alias] = orig.split(".")[-1]
            return updated_node.with_changes(asname=None)
        return updated_node

    def leave_Attribute(self, original_node: cst.Attribute, updated_node: cst.Attribute):
        # e.g., o.system(...) -> os.system(...)
        if m.matches(updated_node.value, m.Name()):
            base = updated_node.value.value  # type: ignore
            if base in self.alias_map:
                return updated_node.with_changes(value=cst.Name(self.alias_map[base]))
        return updated_node

    def leave_Name(self, original_node: cst.Name, updated_node: cst.Name):
        if updated_node.value in self.alias_map:
            return cst.Name(self.alias_map[updated_node.value])
        return updated_node

class CallCanonicalizer(cst.CSTTransformer):
    """
    - Canonicalize keyword args order for key calls
    - Make boolean parameters explicit (e.g., shell=True/False)
    - Provide a consistent argument layout
    """
    def leave_Call(self, original_node: cst.Call, updated_node: cst.Call):
        func_name = cst.helpers.get_full_name_for_node(updated_node.func) or ""
        keywords = list(updated_node.args)

        if func_name in {"subprocess.run", "subprocess.Popen", "subprocess.call", "os.system"}:
            names = [a.keyword.value if a.keyword else None for a in keywords]
            if "shell" not in names and func_name != "os.system":
                keywords.append(cst.Arg(keyword=cst.Name("shell"), value=cst.Name("False")))
            kw = [a for a in keywords if a.keyword]
            pos = [a for a in keywords if not a.keyword]
            kw_sorted = sorted(kw, key=lambda a: a.keyword.value)  # type: ignore
            return updated_node.with_changes(args=[*pos, *kw_sorted])

        return updated_node

class StringNormalizer(cst.CSTTransformer):
    def leave_SimpleString(self, original_node: cst.SimpleString, updated_node: cst.SimpleString):
        s = original_node.evaluated_value
        # normalize to double quotes with proper escaping
        escaped = s.replace("\\", "\\\\").replace('"', '\\"')
        return cst.SimpleString('"' + escaped + '"')

def canonicalize_code(code: str) -> str:
    try:
        mod = cst.parse_module(code)
        transformers = [ImportAliasNormalizer(), CallCanonicalizer(), StringNormalizer()]
        for t in transformers:
            mod = mod.visit(t)
        return mod.code
    except Exception:
        # on parse error, return original
        return code

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="out", required=True)
    args = ap.parse_args()
    inp = pathlib.Path(args.inp)
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    code = inp.read_text(encoding="utf-8", errors="ignore")
    canon = canonicalize_code(code)
    out.write_text(canon, encoding="utf-8")

if __name__ == "__main__":
    main()