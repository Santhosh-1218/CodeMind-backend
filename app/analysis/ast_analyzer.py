import ast
import re
import logging
from typing import List, Dict, Any

logger = logging.getLogger("codemind.analysis.ast")

class SecurityASTVisitor(ast.NodeVisitor):
    def __init__(self, file_path: str, lines: List[str]):
        self.file_path = file_path
        self.lines = lines
        self.findings: List[Dict[str, Any]] = []
        self.unstr_vars: Dict[str, str] = {} # Variable name -> reason

    def get_snippet(self, lineno: int) -> str:
        if 1 <= lineno <= len(self.lines):
            return self.lines[lineno - 1].strip()
        return ""

    def visit_Assign(self, node: ast.Assign):
        # Track variable assignments that contain string formatting or f-strings
        is_unparam = False
        reason = ""

        if isinstance(node.value, ast.JoinedStr):
            is_unparam = True
            reason = "f-string interpolation"
        elif isinstance(node.value, ast.BinOp) and isinstance(node.value.op, (ast.Mod, ast.Add)):
            is_unparam = True
            reason = "string concatenation or % formatting"
        elif isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute) and node.value.func.attr == "format":
            is_unparam = True
            reason = ".format() string formatting"

        if is_unparam:
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self.unstr_vars[target.id] = reason

        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        # 1. SQL Injection Detection in execute()
        func_name = ""
        if isinstance(node.func, ast.Attribute):
            func_name = node.func.attr
        elif isinstance(node.func, ast.Name):
            func_name = node.func.id

        if func_name in ("execute", "executemany") and node.args:
            first_arg = node.args[0]
            has_params = len(node.args) > 1 or len(node.keywords) > 0

            is_unparameterized = False
            reason = ""

            if isinstance(first_arg, ast.JoinedStr):
                is_unparameterized = True
                reason = "f-string interpolation in raw SQL execute call"
            elif isinstance(first_arg, ast.BinOp) and isinstance(first_arg.op, (ast.Mod, ast.Add)):
                is_unparameterized = True
                reason = "String concatenation or % formatting in raw SQL execute call"
            elif isinstance(first_arg, ast.Call) and isinstance(first_arg.func, ast.Attribute) and first_arg.func.attr == "format":
                is_unparameterized = True
                reason = ".format() string formatting in raw SQL execute call"
            elif isinstance(first_arg, ast.Name) and first_arg.id in self.unstr_vars:
                is_unparameterized = True
                reason = f"Variable '{first_arg.id}' constructed via {self.unstr_vars[first_arg.id]}"

            if is_unparameterized and not has_params:
                lineno = getattr(node, 'lineno', 1)
                snippet = self.get_snippet(lineno)
                self.findings.append({
                    "rule_id": "AST-SEC-SQLI",
                    "title": "Unsanitized SQL String Interpolation",
                    "severity": "Critical",
                    "category": "Security",
                    "file_path": self.file_path,
                    "line_number": lineno,
                    "line_end": getattr(node, 'end_lineno', lineno),
                    "snippet": snippet,
                    "description": f"Direct concatenation into raw SQL execution creates a severe SQL injection vulnerability ({reason}).",
                    "rationale": "Allows attackers to inject malicious SQL code, potentially leading to unauthorized data access, data modification, or complete database compromise.",
                    "fix_recommendation": f"- {snippet}\n+ cursor.execute('SELECT * FROM table WHERE field = ?', (user_input,))",
                    "confidence": 95,
                    "evidence": ["Detected by Python AST ASTVisitor Analysis", "Confirmed unparameterized SQL query execution"]
                })

        # 2. Unsafe Subprocess & Command Execution
        if func_name in ("system", "popen"):
            if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == "os":
                lineno = getattr(node, 'lineno', 1)
                snippet = self.get_snippet(lineno)
                self.findings.append({
                    "rule_id": "AST-SEC-CMDI",
                    "title": "Unsafe Shell Command Execution (os.system)",
                    "severity": "Critical",
                    "category": "Security",
                    "file_path": self.file_path,
                    "line_number": lineno,
                    "line_end": getattr(node, 'end_lineno', lineno),
                    "snippet": snippet,
                    "description": "Executing shell commands using os.system passes raw strings to the OS shell, enabling command injection.",
                    "rationale": "If user-controlled input reaches os.system, an attacker can execute arbitrary OS commands on the host server.",
                    "fix_recommendation": f"- {snippet}\n+ subprocess.run(['command', arg1, arg2], check=True)",
                    "confidence": 92,
                    "evidence": ["Detected by Python AST ASTVisitor Analysis", "Direct os.system call found"]
                })

        # 3. Unsafe eval / exec
        if func_name in ("eval", "exec"):
            lineno = getattr(node, 'lineno', 1)
            snippet = self.get_snippet(lineno)
            self.findings.append({
                "rule_id": "AST-SEC-EVAL",
                "title": "Dynamic Code Execution (eval/exec)",
                "severity": "High",
                "category": "Security",
                "file_path": self.file_path,
                "line_number": lineno,
                "line_end": getattr(node, 'end_lineno', lineno),
                "snippet": snippet,
                "description": "Dynamic code evaluation via eval() or exec() permits arbitrary code execution.",
                "rationale": "Evaluating dynamic expressions allows arbitrary Python code execution within the application context.",
                "fix_recommendation": "Replace eval/exec with ast.literal_eval() or explicit mapping logic.",
                "confidence": 90,
                "evidence": ["Detected by Python AST ASTVisitor Analysis", "eval/exec function call identified"]
            })

        self.generic_visit(node)

def analyze_python_ast(file_path: str, content: str) -> List[Dict[str, Any]]:
    """
    Parse Python source code using Python's standard `ast` module.
    Returns structured evidence-backed security & quality findings.
    """
    findings = []
    lines = content.splitlines()
    try:
        tree = ast.parse(content, filename=file_path)
        visitor = SecurityASTVisitor(file_path, lines)
        visitor.visit(tree)
        findings.extend(visitor.findings)
    except SyntaxError as e:
        logger.debug(f"Syntax error parsing Python AST for {file_path}: {e}")
    except Exception as e:
        logger.error(f"AST analysis error for {file_path}: {e}")
    return findings
